# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Backfill worker for the period views: generates all completed calendar periods (day, week, month,
year) as immutable files and maintains the segmented manifest.

Runs as a separate process, started by user.historydata.PeriodDataGenerator when work is due:

    python -m user.historybackfill --job <state dir>/job.json

Only one worker (or historyregen) runs at a time (worker.lock). Work is resumable: finished periods
are recorded in the manifest, failures in the unpublished retry state.
See docs/historic-data-contract.md, sections 5 and 7.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time

from user import historyperiods as hp
from user import historywriter as hw
from user.historyconfig import PeriodChartsConfig

log = logging.getLogger(__name__)

JOB_FILE = 'job.json'
WORKER_STATE_FILE = 'worker.json'
FINAL_STATES = ('ok', 'gaps', 'nodata', 'error', 'incompatible')
# A period counts as completed once the archive contains its last record or this grace time has passed.
COMPLETION_GRACE = 3600
FLUSH_SECONDS = 10


def plain(value):
    """configobj sections -> plain JSON-serializable dicts/lists/strings."""
    if isinstance(value, dict):
        return dict((str(k), plain(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def count_records(db_manager, start, end):
    row = db_manager.getSql("SELECT COUNT(*) FROM %s WHERE dateTime > ? AND dateTime <= ?"
                            % db_manager.table_name, (start, end))
    return int(row[0] or 0) if row else 0


def archive_range(db_manager):
    row = db_manager.getSql("SELECT MIN(dateTime), MAX(dateTime) FROM %s" % db_manager.table_name)
    return (row[0], row[1]) if row else (None, None)


class Backfill(object):
    """Backfill logic, independent of process bootstrap (testable with injected dependencies)."""

    def __init__(self, root, state_directory, config, zone, week_start, db_managers, default_binding,
                 sun_events=None, archive_interval=300, build=None, clock=time.time, sleep=time.sleep):
        if build is None:
            from user.historyaggregate import build_period_data as build
        self.root = root
        self.state_directory = state_directory
        self.config = config
        self.zone = zone
        self.week_start = int(week_start)
        self.db_managers = db_managers
        self.default_binding = default_binding
        self.sun_events = sun_events
        self.archive_interval = int(archive_interval)
        self.build = build
        self.clock = clock
        self.sleep = sleep
        self.retry = hw.RetryState(state_directory, config.max_retries, config.retry_backoff)
        self.manifest = None
        self.stop_requested = False

    # -----------------------------------------------------------------------------------------

    def tasks(self, first, last, now):
        """Completed calendar periods covering the archive, newest first.

        Returns (tasks, next_check): tasks = [(period, start_date, (start, end))]; next_check = time when
        the next period becomes complete.
        """
        tasks = []
        next_check = None
        if first is None:
            return tasks, None
        first_date = self.zone.local(first - 1).date()
        for period in hp.PERIODS:
            current = hp.current_period(self.zone, period, now, self.week_start)
            last_date = hp.previous_period_date(period, current, self.week_start)
            if hp.period_span(self.zone, period, last_date)[1] <= first:
                continue
            for start_date in hp.iter_periods(period, first_date, last_date, self.week_start, newest_first=True):
                span = hp.period_span(self.zone, period, start_date)
                if span[1] <= first:
                    break
                if span[1] > (last or 0) and span[1] + COMPLETION_GRACE > now:
                    # end not yet in the archive, maybe the last record is still being written
                    candidate = span[1] + COMPLETION_GRACE
                    next_check = candidate if next_check is None else min(next_check, candidate)
                    continue
                tasks.append((period, start_date, span))
            end_of_current = hp.period_span(self.zone, period, current)[1]
            next_check = end_of_current if next_check is None else min(next_check, end_of_current)
        tasks.sort(key=lambda t: (-t[2][1], hp.PERIODS.index(t[0])))
        return tasks, next_check

    def _handle_week_start_change(self):
        previous = self.manifest.previous_week_start
        if previous is None or previous == self.week_start:
            return
        log.warning("week_start changed from %s to %s: week files marked incompatible, "
                    "run 'python -m user.historyregen --period week' to regenerate them", previous, self.week_start)
        for pid, entry in self.manifest.entries('week').items():
            if entry.get('s') in ('ok', 'gaps'):
                self.manifest.set('week', pid, {'s': 'incompatible'})
            else:
                self.manifest.remove('week', pid)
        self.retry.clear('week')

    def process(self, period, start_date, span, now):
        """Generate one completed period. Returns the manifest entry (raises on technical failure)."""
        pid = hp.period_id(period, start_date)
        if count_records(self.db_managers(self.default_binding), span[0], span[1]) == 0:
            hw.remove_period_file(self.root, period, pid)
            return {'s': 'nodata'}
        series, observations = self.config.view_plan(period)
        data = self.build(self.db_managers, self.default_binding, series, observations, self.zone, 'calendar',
                          period, pid, span, max(now, span[1]), week_start=self.week_start,
                          sun_events=self.sun_events, fallback_interval=self.archive_interval,
                          gap_threshold=self.config.gap_threshold)
        entry = hw.publish_period(self.root, data, list(observations))
        if entry['s'] == 'nodata':
            hw.remove_period_file(self.root, period, pid)
        return entry

    def run(self, lock=None):
        """Process all outstanding periods. Returns the worker state dict (also saved to worker.json)."""
        self.manifest = hw.Manifest(self.root, self.week_start)
        self._handle_week_start_change()
        first, last = archive_range(self.db_managers(self.default_binding))
        self.manifest.set_archive(first, last)
        now = int(self.clock())
        tasks, next_check = self.tasks(first, last, now)
        weeks_blocked = any(e.get('s') == 'incompatible' for e in self.manifest.entries('week').values())
        if weeks_blocked:
            tasks = [t for t in tasks if t[0] != 'week']

        def finished(period, pid):
            entry = self.manifest.get(period, pid)
            return entry is not None and entry.get('s') in FINAL_STATES

        total = len(tasks)
        done = sum(1 for p, d, _ in tasks if finished(p, hp.period_id(p, d)))
        self.manifest.set_backfill('running' if done < total else 'done', done, total, now)
        self.manifest.flush(now)
        last_flush = self.clock()
        next_retry = None

        for period, start_date, span in tasks:
            if self.stop_requested:
                break
            pid = hp.period_id(period, start_date)
            if finished(period, pid):
                continue
            now = int(self.clock())
            if self.retry.exhausted(period, pid):
                self.manifest.set(period, pid, {'s': 'error', 'tries': self.retry.tries(period, pid)})
                done += 1
                continue
            if not self.retry.due(period, pid, now):
                item = self.retry.data.get('%s/%s' % (period, pid), {})
                next_retry = item.get('next') if next_retry is None else min(next_retry, item.get('next', next_retry))
                continue
            try:
                entry = self.process(period, start_date, span, now)
                self.retry.clear(period, pid)
            except Exception as e:
                tries = self.retry.failure(period, pid, now, e)
                log.error("Backfill of %s %s failed (try %d of %d): %s", period, pid, tries,
                          self.config.max_retries, e, exc_info=True)
                if tries >= self.config.max_retries:
                    entry = {'s': 'error', 'tries': tries}
                else:
                    item = self.retry.data['%s/%s' % (period, pid)]
                    next_retry = item['next'] if next_retry is None else min(next_retry, item['next'])
                    entry = None
            if entry is not None:
                self.manifest.set(period, pid, entry)
                done += 1
            if lock is not None:
                lock.refresh()
            if self.clock() - last_flush >= FLUSH_SECONDS:
                self.manifest.set_backfill('running', done, total, int(self.clock()))
                self.manifest.flush(int(self.clock()))
                last_flush = self.clock()
            if self.config.backfill_pause > 0:
                self.sleep(self.config.backfill_pause)

        now = int(self.clock())
        state = 'done' if done >= total else 'idle'
        self.manifest.set_backfill(state, done, total, now)
        self.manifest.flush(now)
        checks = [c for c in (next_check, next_retry) if c is not None]
        worker_state = {'config': self.config_hash(), 'state': state, 'finished': now,
                        'next_check': min(checks) if checks else None}
        if self.stop_requested:
            worker_state['next_check'] = now
        hw.write_json(os.path.join(self.state_directory, WORKER_STATE_FILE), worker_state)
        log.info("Backfill %s: %d of %d periods finished", state, done, total)
        return worker_state

    def config_hash(self):
        from user.historydata import config_hash
        return config_hash(self.config, self.week_start, self.zone)


# ---------------------------------------------------------------------------------------------
# Start from the report generator
# ---------------------------------------------------------------------------------------------

def needs_run(state_directory, current_hash, now):
    try:
        state = hw.read_json(os.path.join(state_directory, WORKER_STATE_FILE))
    except (OSError, ValueError):
        state = None
    if not state or state.get('config') != current_hash:
        return True
    if state.get('state') != 'done' and state.get('next_check') is None:
        return True
    next_check = state.get('next_check')
    return next_check is not None and now >= next_check


def write_job(state_directory, job):
    return hw.write_json(os.path.join(state_directory, JOB_FILE), plain(job))


def spawn(state_directory):
    """Start a detached worker process; it inherits the module search path of weewxd."""
    lock = hw.WorkerLock(state_directory)
    if os.path.exists(lock.path) and not lock.is_stale():
        log.debug("Backfill worker already running")
        return None
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(p for p in sys.path if p)
    kwargs = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL,
              'env': env, 'close_fds': True}
    if os.name == 'nt':
        kwargs['creationflags'] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True
    cmd = [sys.executable, '-m', 'user.historybackfill', '--job', os.path.join(state_directory, JOB_FILE)]
    log.info("Starting backfill worker: %s", ' '.join(cmd))
    return subprocess.Popen(cmd, **kwargs)


# ---------------------------------------------------------------------------------------------
# Process bootstrap
# ---------------------------------------------------------------------------------------------

class Environment(object):
    """WeeWX configuration, logging and database access for worker / CLI processes."""

    def __init__(self, config_path, process_name):
        import weecfg
        import weeutil.logger
        import weeutil.startup
        import weewx.manager
        self.config_path, self.config_dict = weecfg.read_config(config_path)
        weeutil.logger.setup(process_name, self.config_dict)
        weeutil.startup.initialize(self.config_dict)
        self.binder = weewx.manager.DBBinder(self.config_dict)

    def close(self):
        self.binder.close()


def backfill_from_job(job, environment, lock):
    from user.historyaggregate import SunEventProvider
    config = PeriodChartsConfig(job['period_charts'], job['default_binding'])
    week_start = int(job['week_start'])
    zone = hp.StationZone.detect()
    sun_events = SunEventProvider(environment.config_dict, job.get('skin', {}), config.show_daynight,
                                  config.transition_angle)
    archive_interval = int(environment.config_dict.get('StdArchive', {}).get('archive_interval', 300))
    worker = Backfill(job['root'], job['state_dir'], config, zone, week_start, environment.binder.get_manager,
                      job['default_binding'], sun_events, archive_interval)
    try:
        import signal

        def request_stop(signum, frame):
            log.info("Backfill worker stopping on signal %s", signum)
            worker.stop_requested = True
        signal.signal(signal.SIGTERM, request_stop)
    except (ImportError, ValueError):
        pass
    return worker.run(lock)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m user.historybackfill',
                                     description='Backfill worker for the fuzzy-archer period views')
    parser.add_argument('--job', required=True, help='job.json written by PeriodDataGenerator')
    args = parser.parse_args(argv)
    with open(args.job, 'r') as f:
        job = json.load(f)
    environment = Environment(job['config_path'], 'weewx-historybackfill')
    try:
        if hasattr(os, 'nice'):
            try:
                os.nice(10)
            except OSError:
                pass
        try:
            lock = hw.WorkerLock(job['state_dir']).acquire()
        except hw.LockBusy as e:
            log.info("Backfill worker not started, lock held by %s", e)
            return 0
        try:
            backfill_from_job(job, environment, lock)
        finally:
            lock.release()
    except Exception as e:
        log.error("Backfill worker failed: %s", e, exc_info=True)
        return 1
    finally:
        environment.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
