# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Report generator for the period views: writes the running calendar periods (current/*) and the
rolling windows (rolling/*) plus current.json. Completed periods are written by the backfill worker.

Add user.historydata.PeriodDataGenerator to [Generators] generator_list and configure [PeriodCharts].
See docs/historic-data-contract.md, sections 2, 4 and 7.
"""

import hashlib
import json
import logging
import os
import time

from user import historyperiods as hp
from user import historywriter as hw
from user.historyconfig import PeriodChartsConfig

log = logging.getLogger(__name__)

# Tolerance for due checks, so a refresh interval of 3600 s is not missed by a few seconds of report jitter.
DUE_TOLERANCE = 30
STATE_FILE = 'generator.json'


def config_hash(config, week_start, zone):
    signature = {'config': config.signature(), 'week_start': int(week_start), 'tz': zone.name,
                 'schema': hw.SCHEMA_VERSION}
    return hashlib.sha1(json.dumps(signature, sort_keys=True).encode('utf-8')).hexdigest()[:16]


def is_due(previous, period_id, refresh, now, force):
    """Due if forced (config change), missing, period rolled over or the refresh interval has elapsed."""
    if force or not previous:
        return True
    if period_id is not None and previous.get('period_id') != period_id:
        return True
    if refresh <= 0:
        return True
    return now - int(previous.get('generated', 0)) >= refresh - DUE_TOLERANCE


def generate_mutable(root, state_directory, config, zone, week_start, now, db_managers, default_binding,
                     sun_events=None, archive_interval=300, build=None):
    """Write all due current/rolling files and current.json. Returns the list of written (kind, period).

    A failed file is logged and not published; its previous entry is kept only if it still describes
    the same running period.
    """
    if build is None:
        from user.historyaggregate import build_period_data as build
    now = int(now)
    state_path = os.path.join(state_directory, STATE_FILE)
    try:
        state = hw.read_json(state_path) or {}
    except (OSError, ValueError):
        state = {}
    current_hash = config_hash(config, week_start, zone)
    force = state.get('config') != current_hash
    if force and state:
        log.info("PeriodDataGenerator: configuration changed, regenerating all current and rolling files")

    previous = hw.read_current_index(root) or {}
    if previous.get('week_start') != int(week_start):
        force = True
    old_current = previous.get('current', {})
    old_rolling = previous.get('rolling', {})
    new_current, new_rolling, written = {}, {}, []

    def refresh_of(period):
        refresh = config.refresh[period]
        return refresh if refresh > 0 else int(archive_interval)

    def produce(kind, period, span, period_id):
        series, observations = config.view_plan(period)
        data = build(db_managers, default_binding, series, observations, zone,
                     'calendar' if kind == 'current' else 'rolling', period, period_id, span, now,
                     week_start=week_start, sun_events=sun_events, fallback_interval=archive_interval)
        rel, rev = hw.write_current_file(root, kind, period, data)
        written.append((kind, period))
        return {'file': rel, 'rev': rev, 'generated': now, 'refresh': refresh_of(period)}

    for period in hp.PERIODS:
        start_date = hp.current_period(zone, period, now, week_start)
        pid = hp.period_id(period, start_date)
        old = old_current.get(period)
        if not is_due(old, pid, config.refresh[period], now, force):
            new_current[period] = dict(old, refresh=refresh_of(period))
            continue
        try:
            entry = produce('current', period, hp.period_span(zone, period, start_date), pid)
            entry['period_id'] = pid
            new_current[period] = entry
        except Exception as e:
            log.error("PeriodDataGenerator: failed to generate current %s %s: %s", period, pid, e, exc_info=True)
            if old and old.get('period_id') == pid and not force:
                new_current[period] = old

    for period in hp.ROLLING_PERIODS:
        old = old_rolling.get(period)
        if not is_due(old, None, config.refresh[period], now, force):
            new_rolling[period] = dict(old, refresh=refresh_of(period))
            continue
        try:
            new_rolling[period] = produce('rolling', period, hp.rolling_window(period, now), None)
        except Exception as e:
            log.error("PeriodDataGenerator: failed to generate rolling %s: %s", period, e, exc_info=True)
            if old and not force:
                new_rolling[period] = old

    hw.write_current_index(root, now, week_start, new_current, new_rolling)
    if state.get('config') != current_hash:
        hw.write_json(state_path, {'config': current_hash})
    return written


def resolve_week_start(config_dict, stn_info=None):
    value = getattr(stn_info, 'week_start', None)
    if value is None:
        value = config_dict.get('Station', {}).get('week_start', 6)
    week_start = int(value)
    if not 0 <= week_start <= 6:
        raise ValueError("week_start must be 0..6, got %s" % value)
    return week_start


try:
    import weewx.reportengine

    class PeriodDataGenerator(weewx.reportengine.ReportGenerator):
        """Writes current and rolling period files of [PeriodCharts]."""

        def run(self):
            section = self.skin_dict.get('PeriodCharts')
            if not section:
                log.info("PeriodDataGenerator: no [PeriodCharts] section, nothing to do")
                return
            default_binding = self.skin_dict.get('data_binding', 'wx_binding')
            config = PeriodChartsConfig(section, default_binding)
            if not config.generate:
                log.debug("PeriodDataGenerator: generate = false for report %s", self.skin_dict.get('REPORT_NAME'))
                return
            if not config.charts:
                log.warning("PeriodDataGenerator: [PeriodCharts] contains no valid chart")
                return

            from user.historyaggregate import SunEventProvider
            start_time = time.time()
            html_root = os.path.join(self.config_dict['WEEWX_ROOT'], self.skin_dict['HTML_ROOT'])
            root = hw.data_root(html_root)
            state_directory = hw.state_dir(self.config_dict, root, config.state_root)
            week_start = resolve_week_start(self.config_dict, self.stn_info)
            zone = hp.StationZone.detect()
            archive_interval = int(self.config_dict.get('StdArchive', {}).get('archive_interval', 300))
            sun_events = SunEventProvider(self.config_dict, self.skin_dict, config.show_daynight,
                                          config.transition_angle)
            written = generate_mutable(root, state_directory, config, zone, week_start, time.time(),
                                       self.db_binder.get_manager, default_binding, sun_events,
                                       archive_interval)
            log.info("PeriodDataGenerator: wrote %d current/rolling files for %s in %.2f seconds",
                     len(written), self.skin_dict.get('REPORT_NAME'), time.time() - start_time)
            self.start_worker(root, state_directory, config)

        def start_worker(self, root, state_directory, config):
            """Start the backfill worker process when work is due (it never blocks the report)."""
            from user import historybackfill
            try:
                week_start = resolve_week_start(self.config_dict, self.stn_info)
                current_hash = config_hash(config, week_start, hp.StationZone.detect())
                if not historybackfill.needs_run(state_directory, current_hash, time.time()):
                    return
                config_path = self.config_dict.get('config_path')
                if not config_path:
                    log.warning("PeriodDataGenerator: config_path unknown, backfill worker not started")
                    return
                historybackfill.write_job(state_directory, {
                    'config_path': config_path,
                    'root': root,
                    'state_dir': state_directory,
                    'default_binding': self.skin_dict.get('data_binding', 'wx_binding'),
                    'week_start': week_start,
                    'period_charts': self.skin_dict['PeriodCharts'],
                    'skin': {'Skyfield': self.skin_dict.get('Skyfield', {})},
                })
                historybackfill.spawn(state_directory)
            except Exception as e:
                log.error("PeriodDataGenerator: could not start backfill worker: %s", e, exc_info=True)

except ImportError:  # pragma: no cover - only without WeeWX (pure unit tests)
    PeriodDataGenerator = None
