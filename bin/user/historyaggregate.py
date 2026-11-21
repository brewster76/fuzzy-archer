# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Computation of period file content (series, statistics, coverage, sun events) from the WeeWX database.

See docs/historic-data-contract.md, sections 1 and 3. Any database/xtypes error propagates to the
caller: a failed series fails the whole period (never published as gap).
"""

import bisect
import logging
import math
import os
import sys

import weewx
import weewx.units
import weewx.xtypes
from weeutil.weeutil import TimeSpan

from user.historyperiods import NATIVE, buckets

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
WIND_COMPONENTS = ('windDir', 'windSpeed')


def clean(value):
    """JSON-safe number: None for missing/NaN/Infinity, floats reduced to 7 significant digits."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    rounded = float('%.7g' % value)
    return int(rounded) if rounded.is_integer() and abs(rounded) < 1e15 else rounded


def stat_obs_type(data_type, statistic):
    """Vector statistics of wind components are computed on WeeWX observation 'wind'."""
    if statistic in ('vecavg', 'vecdir') and data_type in WIND_COMPONENTS:
        return 'wind'
    return data_type


def standard_unit(db_manager, obs_type, aggregate_type=None):
    try:
        return weewx.units.getStandardUnitType(db_manager.std_unit_system, obs_type, aggregate_type)
    except Exception:
        return None, None


class Coverage(object):
    def __init__(self, first, last, records, archive_interval, expected):
        self.first = first
        self.last = last
        self.records = records
        self.archive_interval = archive_interval
        self.expected = expected

    def to_dict(self):
        return {'first': self.first, 'last': self.last, 'records': self.records,
                'expected': self.expected, 'archive_interval': self.archive_interval}


def get_coverage(db_manager, start, end, generated, fallback_interval=None):
    """Archive records in (start, min(end, generated)] (contract 3, 3.1)."""
    stop = min(end, generated)
    table = db_manager.table_name
    row = db_manager.getSql("SELECT MIN(dateTime), MAX(dateTime), COUNT(*) FROM %s "
                            "WHERE dateTime > ? AND dateTime <= ?" % table, (start, stop))
    first, last, records = (row[0], row[1], int(row[2] or 0)) if row else (None, None, 0)
    archive_interval = None
    if records:
        row = db_manager.getSql("SELECT interval, COUNT(*) AS c FROM %s WHERE dateTime > ? AND dateTime <= ? "
                                "GROUP BY interval ORDER BY c DESC, interval ASC LIMIT 1" % table,
                                (start, stop))
        if row and row[0]:
            archive_interval = int(round(row[0] * 60))
    if archive_interval is None and fallback_interval:
        archive_interval = int(fallback_interval)
    expected = int(max(0, stop - start) // archive_interval) if archive_interval else records
    return Coverage(first, last, records, archive_interval, expected)


def record_times(db_manager, start, end):
    """Sorted timestamps of all archive records in (start, end]."""
    return [r[0] for r in db_manager.genSql("SELECT dateTime FROM %s WHERE dateTime > ? AND dateTime <= ? "
                                            "ORDER BY dateTime" % db_manager.table_name, (start, end))]


class _RecordIndex(object):
    """Fast 'has the bucket (a, b] any record' test, so empty buckets cost no aggregate query."""

    def __init__(self, times):
        self.times = times

    def any_in(self, a, b):
        i = bisect.bisect_right(self.times, a)
        return i < len(self.times) and self.times[i] <= b


def native_series(db_manager, data_type, start, end):
    """[[start, end, value], ...] and (unit, group) for the archive records in (start, end]."""
    start_vt, stop_vt, data_vt = weewx.xtypes.get_series(data_type, TimeSpan(start, end), db_manager)
    points = [[int(a), int(b), clean(v)] for a, b, v in zip(start_vt[0], stop_vt[0], data_vt[0])]
    unit, group = data_vt[1], data_vt[2]
    if unit is None:
        unit, group = standard_unit(db_manager, data_type)
    return points, unit, group


def aggregated_series(db_manager, data_type, aggregate_type, resolution, zone, axis_start, axis_end,
                      generated, coverage_last, running, record_index):
    """Points for every grid bucket intersecting the axis (full nominal spans, contract 1.5)."""
    points = []
    unit, group = None, None
    provisional_after = coverage_last if coverage_last is not None else axis_start
    for a, b in buckets(zone, resolution, axis_start, axis_end):
        value = None
        if a < generated and (aggregate_type == 'count' or record_index.any_in(a, min(b, generated))):
            vt = weewx.xtypes.get_aggregate(data_type, TimeSpan(a, b), aggregate_type, db_manager)
            value = clean(vt[0])
            if vt[1] is not None:
                if unit is not None and (vt[1], vt[2]) != (unit, group):
                    raise weewx.UnsupportedFeature("Unit of %s changes within series" % data_type)
                unit, group = vt[1], vt[2]
        point = [a, b, value]
        if running and b > provisional_after:
            point.append(1)
        points.append(point)
    if unit is None:
        unit, group = standard_unit(db_manager, data_type, aggregate_type)
    return points, unit, group


def observation_stats(db_manager, data_type, statistics, start, end):
    """Statistics over exactly (start, end] (contract 1.6, 3.5)."""
    span = TimeSpan(start, end)
    unit, group = standard_unit(db_manager, data_type)
    stats = {}
    stat_units = {}
    for statistic in statistics:
        obs_type = stat_obs_type(data_type, statistic)
        vt = weewx.xtypes.get_aggregate(obs_type, span, statistic, db_manager)
        value = clean(vt[0])
        if statistic in ('min', 'max'):
            if value is None:
                stats[statistic] = None
            else:
                time_vt = weewx.xtypes.get_aggregate(obs_type, span, statistic + 'time', db_manager)
                stats[statistic] = [value, int(time_vt[0])] if time_vt[0] is not None else None
        else:
            stats[statistic] = value
        if vt[1] is not None and (vt[1], vt[2]) != (unit, group):
            stat_units[statistic] = [vt[1], vt[2]]
    count_type = 'windSpeed' if data_type == 'wind' else data_type
    count = weewx.xtypes.get_aggregate(count_type, span, 'count', db_manager)[0]
    return unit, group, int(count or 0), stats, stat_units


def darkening_extent(angle, transition_angle):
    """Same formula as jsonengine.get_day_night_events."""
    if angle >= transition_angle:
        return 0
    if angle <= -transition_angle:
        return 1
    return abs(((angle - transition_angle) / 2.0) / transition_angle)


class SunEventProvider(object):
    """Sun events for the axis range (contract 3.6). Returns [] when disabled or skyfield is missing."""

    def __init__(self, config_dict, skin_dict, show_daynight, transition_angle):
        self.config_dict = config_dict
        self.skin_dict = skin_dict
        self.show_daynight = show_daynight
        self.transition_angle = transition_angle
        self._warned = False

    def available(self):
        if not self.show_daynight:
            return False
        if 'skyfield' not in sys.modules:
            try:
                import skyfield.api  # noqa: F401
            except ImportError:
                if not self._warned:
                    log.info("skyfield not available: period charts are drawn without day/night background")
                    self._warned = True
                return False
        return True

    def __call__(self, start, end):
        if not self.available():
            return []
        from user.sunevents import SunEvents
        station = self.config_dict['Station']
        altitude = station.get('altitude', [0, 'meter'])
        altitude_m = float(altitude[0])
        if len(altitude) > 1 and altitude[1] == 'foot':
            altitude_m = weewx.units.convert((altitude_m, 'foot', 'group_altitude'), 'meter')[0]
        sqlite_root = self.config_dict.get('DatabaseTypes', {}).get('SQLite', {}).get('SQLITE_ROOT', '.')
        path = os.path.join(self.config_dict.get('WEEWX_ROOT', '.'), sqlite_root, 'skyfield')
        os.makedirs(path, exist_ok=True)
        ephemeris = self.skin_dict.get('Skyfield', {}).get('ephemeris', 'de440s.bsp')
        events = SunEvents(start, end, station['longitude'], station['latitude'], int(altitude_m), path,
                           ephemeris).get_transits(self.transition_angle)
        result = []
        for event in events or []:
            result.append([int(event[0]), clean(darkening_extent(event[1], self.transition_angle)), event[2]])
        return result


def build_period_data(db_managers, default_binding, series_plan, observation_plan, zone, kind, period,
                      period_id, span, generated, week_start=None, sun_events=None, fallback_interval=None):
    """Assemble a complete period file dict (contract 3).

    db_managers: callable binding -> db_manager.
    span: (start, end) of the calendar period or rolling window; axis = span.
    """
    start, end = int(span[0]), int(span[1])
    generated = int(generated)
    running = kind == 'rolling' or generated < end
    main_manager = db_managers(default_binding)
    coverage = get_coverage(main_manager, start, end, generated, fallback_interval)

    record_indexes = {}

    def record_index(binding, a, b):
        cache_key = (binding, a, b)
        if cache_key not in record_indexes:
            record_indexes[cache_key] = _RecordIndex(record_times(db_managers(binding), a, b))
        return record_indexes[cache_key]

    series = {}
    for key, vs in series_plan.items():
        manager = db_managers(vs.binding)
        if vs.resolution == NATIVE:
            points, unit, group = native_series(manager, vs.data_type, start, min(end, generated))
        else:
            grid = buckets(zone, vs.resolution, start, end)
            if not grid:
                points, unit, group = [], None, None
            else:
                index = record_index(vs.binding, grid[0][0], grid[-1][1])
                points, unit, group = aggregated_series(manager, vs.data_type, vs.aggregate_type, vs.resolution,
                                                        zone, start, end, generated, coverage.last, running, index)
        series[key] = {'observation': vs.obs_key, 'aggregate_type': vs.aggregate_type or 'none',
                       'resolution': vs.resolution, 'unit': unit, 'group': group, 'points': points}

    observations = {}
    for obs_key, obs in observation_plan.items():
        manager = db_managers(obs['data_binding'])
        unit, group, count, stats, stat_units = observation_stats(manager, obs['data_type'], obs['statistics'],
                                                                  start, min(end, generated))
        entry = {'data_binding': obs['data_binding'], 'data_type': obs['data_type'], 'unit': unit,
                 'group': group, 'count': count, 'stats': stats}
        if stat_units:
            entry['stat_units'] = stat_units
        observations[obs_key] = entry

    if running:
        state = 'running'
    else:
        state = 'gaps' if coverage.records < coverage.expected else 'complete'

    data = {
        'schema_version': SCHEMA_VERSION,
        'time_unit': 's',
        'kind': kind,
        'period': period,
        'period_id': period_id if kind == 'calendar' else None,
        'state': state,
        'timezone': {'name': zone.name, 'transitions': zone.transitions(start, end)},
        'generated': generated,
        'period_span': {'start': start, 'end': end},
        'axis': {'start': start, 'end': end},
        'coverage': coverage.to_dict(),
        'unit_system': main_manager.std_unit_system,
        'observations': observations,
        'series': series,
        'sun_events': sun_events(start, end) if (sun_events and period in ('day', 'week')) else [],
        'errors': [],
    }
    if period == 'week':
        data['week_start'] = int(week_start)
    return data
