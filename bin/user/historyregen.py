# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Regenerate completed period files of the fuzzy-archer period views.

Use after correcting archive data, changing [PeriodCharts] or the station's week_start, or to retry
periods in the manifest state 'error':

    python -m user.historyregen --period week
    python -m user.historyregen --period day month --from 2024-03-01 --to 2024-05-31
    python -m user.historyregen --period all --series rain
    python -m user.historyregen --period year --dry-run

--from / --to accept YYYY, YYYY-MM or YYYY-MM-DD (default: whole archive); every completed period
overlapping the range is regenerated. --series KEY restricts regeneration to periods whose existing file
lacks a series of the current configuration matching KEY (observation type, binding/type or full series
key), e.g. after adding a chart. Takes the same lock as the backfill worker (exit code 2 if busy).
See docs/historic-data-contract.md, sections 5 and 7.
"""

import argparse
import calendar
import datetime as dt
import logging
import os
import sys
import time

from user import historyperiods as hp
from user import historywriter as hw
from user.historybackfill import Backfill, Environment, WORKER_STATE_FILE, archive_range
from user.historyconfig import PeriodChartsConfig

log = logging.getLogger(__name__)

GENERATOR_CLASS = 'user.historydata.PeriodDataGenerator'
GENERATOR_STATE_FILE = 'generator.json'
EXIT_OK, EXIT_FAILED, EXIT_BUSY, EXIT_USAGE = 0, 1, 2, 3


def parse_date(value, end=False):
    """YYYY, YYYY-MM or YYYY-MM-DD -> first (or with end=True last) local date covered."""
    parts = value.split('-')
    try:
        numbers = [int(p) for p in parts]
        if len(numbers) == 1:
            return dt.date(numbers[0], 12, 31) if end else dt.date(numbers[0], 1, 1)
        if len(numbers) == 2:
            last = calendar.monthrange(numbers[0], numbers[1])[1]
            return dt.date(numbers[0], numbers[1], last if end else 1)
        if len(numbers) == 3:
            return dt.date(*numbers)
    except ValueError:
        pass
    raise ValueError("Invalid date '%s' (expected YYYY, YYYY-MM or YYYY-MM-DD)" % value)


def series_matches(key, selector):
    binding, obs_type = key.split('/')[:2]
    return selector in (key, obs_type, '%s/%s' % (binding, obs_type))


def lacks_series(root, entry, keys):
    """True if the published file of a manifest entry misses one of the series keys."""
    if not entry or entry.get('s') not in ('ok', 'gaps') or not entry.get('file'):
        return True
    try:
        data = hw.read_json(os.path.join(root, *entry['file'].split('/')))
    except (OSError, ValueError):
        return True
    return any(key not in data.get('series', {}) for key in keys)


def _in_range(period, start_date, from_date, to_date):
    if from_date is not None and hp.next_period_date(period, start_date) <= from_date:
        return False
    return to_date is None or start_date <= to_date


def _remove_old_weeks(worker, periods, from_date, to_date, dry_run):
    removed = []
    if 'week' not in periods:
        return removed
    for pid, entry in sorted(worker.manifest.entries('week').items()):
        start_date = hp.parse_period_id('week', pid)
        aligned = start_date.weekday() == worker.week_start
        outdated = entry.get('s') == 'incompatible' or not aligned
        if outdated and _in_range('week', start_date, from_date, to_date):
            removed.append(pid)
            if not dry_run:
                hw.remove_period_file(worker.root, 'week', pid)
                worker.manifest.remove('week', pid)
                worker.retry.clear('week', pid)
    return removed


def _filter_series_tasks(worker, tasks, series):
    selected = []
    for period, start_date, span in tasks:
        keys = [key for key in worker.config.view_plan(period)[0]
                if any(series_matches(key, selector) for selector in series)]
        pid = hp.period_id(period, start_date)
        if keys and lacks_series(worker.root, worker.manifest.get(period, pid), keys):
            selected.append((period, start_date, span))
    return selected


def _process_tasks(worker, tasks, result):
    last_flush = worker.clock()
    for period, start_date, span in tasks:
        if worker.stop_requested:
            break
        pid = hp.period_id(period, start_date)
        try:
            entry = worker.process(period, start_date, span, int(worker.clock()))
        except Exception as e:
            log.exception("Regeneration of %s %s failed", period, pid)
            result['failed'].append((period, pid, str(e)))
            continue
        worker.manifest.set(period, pid, entry)
        worker.retry.clear(period, pid)
        result['regenerated'].append((period, pid, entry['s']))
        if worker.clock() - last_flush >= 10:
            worker.manifest.flush(int(worker.clock()))
            last_flush = worker.clock()
    worker.manifest.flush(int(worker.clock()))


def _clear_generator_state(worker):
    for name in (WORKER_STATE_FILE, GENERATOR_STATE_FILE):
        try:
            os.unlink(os.path.join(worker.state_directory, name))
        except FileNotFoundError:
            pass


def regenerate(worker, periods, from_date=None, to_date=None, series=None, now=None, dry_run=False):
    """Regenerate completed periods with a Backfill instance. Returns a result dict.

    Old week files (incompatible or not aligned with the current week_start) overlapping the range are
    removed, error states and retry counters of regenerated periods are reset.
    """
    now = int(now if now is not None else worker.clock())
    worker.manifest = hw.Manifest(worker.root, worker.week_start)
    worker._handle_week_start_change()
    first, last = archive_range(worker.db_managers(worker.default_binding))
    worker.manifest.set_archive(first, last)

    tasks, _ = worker.tasks(first, last, now)
    tasks = [task for task in tasks if task[0] in periods
             and _in_range(task[0], task[1], from_date, to_date)]
    removed = _remove_old_weeks(worker, periods, from_date, to_date, dry_run)

    if series:
        tasks = _filter_series_tasks(worker, tasks, series)

    result = {'planned': [(p, hp.period_id(p, d)) for p, d, _ in tasks], 'removed_weeks': removed,
              'regenerated': [], 'failed': []}
    if dry_run:
        return result

    _process_tasks(worker, tasks, result)
    _clear_generator_state(worker)
    return result


# ---------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------

def find_reports(config_dict, report=None):
    """[(report name, skin_dict)] of reports generating period data (generate = true)."""
    import weeutil.weeutil
    import weewx.reportengine
    names = [report] if report else [s for s in config_dict['StdReport'].sections if s != 'Defaults']
    found = []
    for name in names:
        if name not in config_dict['StdReport']:
            raise ValueError("Report '%s' not found in [StdReport]" % name)
        if not report and 'skin' not in config_dict['StdReport'][name]:
            continue
        skin_dict = weewx.reportengine.build_skin_dict(config_dict, name)
        generators = weeutil.weeutil.option_as_list(skin_dict.get('Generators', {}).get('generator_list', []))
        section = skin_dict.get('PeriodCharts')
        if GENERATOR_CLASS in generators and section is not None:
            if PeriodChartsConfig(section, skin_dict.get('data_binding', 'wx_binding')).generate:
                found.append((name, skin_dict))
    return found


def build_parser():
    parser = argparse.ArgumentParser(prog='python -m user.historyregen',
                                     description='Regenerate completed period files of the fuzzy-archer '
                                                 'period views (day, week, month, year).')
    parser.add_argument('--config', help='weewx.conf (default: standard locations)')
    parser.add_argument('--report', help='report in [StdReport] (default: the report generating period data)')
    parser.add_argument('--period', required=True, nargs='+', choices=list(hp.PERIODS) + ['all'],
                        help='period types to regenerate')
    parser.add_argument('--from', dest='from_date', help='first date: YYYY, YYYY-MM or YYYY-MM-DD')
    parser.add_argument('--to', dest='to_date', help='last date: YYYY, YYYY-MM or YYYY-MM-DD')
    parser.add_argument('--series', nargs='+',
                        help='only periods whose file lacks a matching series (type, binding/type or series key)')
    parser.add_argument('--dry-run', action='store_true', help='only list what would be regenerated')
    return parser


def _parse_date_range(args):
    try:
        from_date = parse_date(args.from_date) if args.from_date else None
        to_date = parse_date(args.to_date, end=True) if args.to_date else None
    except ValueError as e:
        print(e, file=sys.stderr)
        return None
    if from_date and to_date and from_date > to_date:
        print("--from is after --to", file=sys.stderr)
        return None
    return from_date, to_date


def _select_report(config_dict, report):
    try:
        reports = find_reports(config_dict, report)
    except ValueError as e:
        print(e, file=sys.stderr)
        return None
    if not reports:
        print("No report with %s and [PeriodCharts] generate = true found" % GENERATOR_CLASS, file=sys.stderr)
        return None
    if len(reports) > 1:
        print("Several reports generate period data (%s), select one with --report"
              % ', '.join(r[0] for r in reports), file=sys.stderr)
        return None
    return reports[0]


def _build_worker(environment, skin_dict):
    from user.historyaggregate import SunEventProvider
    from user.historydata import resolve_week_start

    config_dict = environment.config_dict
    default_binding = skin_dict.get('data_binding', 'wx_binding')
    config = PeriodChartsConfig(skin_dict['PeriodCharts'], default_binding)
    root = hw.data_root(os.path.join(config_dict['WEEWX_ROOT'], skin_dict['HTML_ROOT']))
    state_directory = hw.state_dir(config_dict, root, config.state_root)
    week_start = resolve_week_start(config_dict)
    zone = hp.StationZone.detect()
    sun_events = SunEventProvider(config_dict, skin_dict, config.show_daynight, config.transition_angle)
    archive_interval = int(config_dict.get('StdArchive', {}).get('archive_interval', 300))
    worker = Backfill(root, state_directory, config, zone, week_start, environment.binder.get_manager,
                      default_binding, sun_events, archive_interval)
    return root, state_directory, worker


def _run_locked(worker, state_directory, args, periods, from_date, to_date):
    lock = None
    if not args.dry_run:
        try:
            lock = hw.WorkerLock(state_directory).acquire()
        except hw.LockBusy as e:
            print("Backfill worker or another regeneration is running (%s), try again later" % e,
                  file=sys.stderr)
            return EXIT_BUSY, None
    try:
        started = time.time()
        result = regenerate(worker, periods, from_date, to_date, args.series, dry_run=args.dry_run)
    finally:
        if lock is not None:
            lock.release()
    return EXIT_OK, (result, started)


def _run_environment(environment, args, periods, from_date, to_date):
    report = _select_report(environment.config_dict, args.report)
    if report is None:
        return EXIT_USAGE, None
    name, skin_dict = report
    root, state_directory, worker = _build_worker(environment, skin_dict)
    status, run_result = _run_locked(worker, state_directory, args, periods, from_date, to_date)
    if status != EXIT_OK:
        return status, None
    result, started = run_result
    return EXIT_OK, (name, root, result, started)


def _print_result(args, name, root, result, started):
    print("Report %s, data root %s" % (name, root))
    if result['removed_weeks']:
        print("%s %d old week files" % ('Would remove' if args.dry_run else 'Removed', len(result['removed_weeks'])))
    if args.dry_run:
        for period, pid in result['planned']:
            print("would regenerate %s %s" % (period, pid))
        print("%d periods would be regenerated" % len(result['planned']))
        return EXIT_OK
    for period, pid, error in result['failed']:
        print("FAILED %s %s: %s" % (period, pid, error), file=sys.stderr)
    print("Regenerated %d of %d periods in %.1f seconds"
          % (len(result['regenerated']), len(result['planned']), time.time() - started))
    return EXIT_FAILED if result['failed'] else EXIT_OK


def main(argv=None):
    args = build_parser().parse_args(argv)
    periods = list(hp.PERIODS) if 'all' in args.period else [p for p in hp.PERIODS if p in args.period]
    date_range = _parse_date_range(args)
    if date_range is None:
        return EXIT_USAGE
    from_date, to_date = date_range

    environment = Environment(args.config, 'weewx-historyregen')
    try:
        status, run_result = _run_environment(environment, args, periods, from_date, to_date)
    finally:
        environment.close()
    if status != EXIT_OK:
        return status
    name, root, result, started = run_result
    return _print_result(args, name, root, result, started)


if __name__ == '__main__':
    sys.exit(main())
