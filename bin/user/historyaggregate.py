# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Computation of period file content (series, statistics, coverage, sun events) from the WeeWX database.

See docs/historic-data-contract.md, sections 1 and 3. Any database/xtypes error propagates to the
caller: a failed series fails the whole period (never published as gap). Exception: series and
observations whose type or aggregation the database does not support are omitted.
"""

import bisect
import datetime
import logging
import math
import os

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


def _aggregate_bucket(db_manager, data_type, aggregate_type, start, end, generated,
                      record_index, unit, group):
    if start >= generated:
        return None, unit, group
    if aggregate_type != 'count' and not record_index.any_in(start, min(end, generated)):
        return None, unit, group
    value_tuple = weewx.xtypes.get_aggregate(data_type, TimeSpan(start, end), aggregate_type, db_manager)
    if value_tuple[1] is not None:
        if unit is not None and (value_tuple[1], value_tuple[2]) != (unit, group):
            raise weewx.UnsupportedFeature("Unit of %s changes within series" % data_type)
        unit, group = value_tuple[1], value_tuple[2]
    return clean(value_tuple[0]), unit, group


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
        value, unit, group = _aggregate_bucket(db_manager, data_type, aggregate_type, a, b, generated,
                                               record_index, unit, group)
        point = [a, b, value]
        if running and b > provisional_after:
            point.append(1)
        points.append(point)
    if unit is None:
        unit, group = standard_unit(db_manager, data_type, aggregate_type)
    return points, unit, group


def daily_summary_span(zone, start, end):
    """(start, end] widened to local midnights: every day it touches, completely."""
    first = zone.day_start(zone.local(start).date())
    last_date = zone.local(end).date()
    last = zone.day_start(last_date)
    if last < end:
        last = zone.day_start(last_date + datetime.timedelta(days=1))
    return TimeSpan(first, last)


def _statistic_value(db_manager, obs_type, statistic, span, extreme_span=None):
    if statistic in ('min', 'max') and extreme_span is not None \
            and obs_type in getattr(db_manager, 'daykeys', ()):
        # Daily summaries also contain LOOP highs/lows; they cover whole days only (contract 1.6).
        span = extreme_span
    value_tuple = weewx.xtypes.get_aggregate(obs_type, span, statistic, db_manager)
    value = clean(value_tuple[0])
    if statistic not in ('min', 'max') or value is None:
        return value_tuple, value
    time_tuple = weewx.xtypes.get_aggregate(obs_type, span, statistic + 'time', db_manager)
    return value_tuple, [value, int(time_tuple[0])] if time_tuple[0] is not None else None


def observation_stats(db_manager, data_type, statistics, start, end, extreme_span=None):
    """Statistics over exactly (start, end]; min/max over extreme_span when given (contract 1.6, 3.5)."""
    span = TimeSpan(start, end)
    unit, group = standard_unit(db_manager, data_type)
    stats = {}
    stat_units = {}
    for statistic in statistics:
        obs_type = stat_obs_type(data_type, statistic)
        value_tuple, value = _statistic_value(db_manager, obs_type, statistic, span, extreme_span)
        stats[statistic] = value
        if value_tuple[1] is not None and (value_tuple[1], value_tuple[2]) != (unit, group):
            stat_units[statistic] = [value_tuple[1], value_tuple[2]]
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


def station_location(config_dict, stn_info=None):
    """[longitude, latitude, altitude in meters].

    Prefers the engine's stn_info, whose altitude may come from the station console; falls back to
    [Station] in weewx.conf for processes without an engine (backfill worker, historyregen).
    """
    if stn_info is not None:
        altitude_m = weewx.units.convert(stn_info.altitude_vt, 'meter')[0]
        return [float(stn_info.longitude_f), float(stn_info.latitude_f), float(altitude_m)]
    station = config_dict['Station']
    altitude = station.get('altitude', [0, 'meter'])
    if isinstance(altitude, str):
        altitude = [altitude, 'meter']
    altitude_m = float(altitude[0])
    if len(altitude) > 1 and altitude[1] == 'foot':
        altitude_m = weewx.units.convert((altitude_m, 'foot', 'group_altitude'), 'meter')[0]
    return [float(station['longitude']), float(station['latitude']), float(altitude_m)]


class SunEventProvider(object):
    """Sun events for the axis range (contract 3.6). Returns [] when disabled; without skyfield the sun
    position is approximated (user.sunevents.compute_sun_events)."""

    def __init__(self, config_dict, skin_dict, show_daynight, transition_angle, location=None):
        """location: [longitude, latitude, altitude_m], see station_location(); None = from weewx.conf."""
        self.config_dict = config_dict
        self.skin_dict = skin_dict
        self.show_daynight = show_daynight
        self.transition_angle = transition_angle
        self.location = location

    def _location(self):
        if self.location is None:
            self.location = station_location(self.config_dict)
        return self.location

    def available(self):
        return bool(self.show_daynight)

    def __call__(self, start, end):
        if not self.available():
            return []
        from user.sunevents import compute_sun_events
        longitude, latitude, altitude_m = self._location()
        sqlite_root = self.config_dict.get('DatabaseTypes', {}).get('SQLite', {}).get('SQLITE_ROOT', '.')
        path = os.path.join(self.config_dict.get('WEEWX_ROOT', '.'), sqlite_root, 'skyfield')
        ephemeris = self.skin_dict.get('Skyfield', {}).get('ephemeris', 'de440s.bsp')
        events = compute_sun_events(start, end, longitude, latitude, int(altitude_m), path, ephemeris,
                                    self.transition_angle)
        result = []
        for event in events or []:
            result.append([int(event[0]), clean(darkening_extent(event[1], self.transition_angle)), event[2]])
        return result


def _record_index(db_managers, cache, binding, start, end):
    cache_key = (binding, start, end)
    if cache_key not in cache:
        cache[cache_key] = _RecordIndex(record_times(db_managers(binding), start, end))
    return cache[cache_key]


_unsupported_warned = set()


def _skip_unsupported(kind, key, error):
    """Unknown observation types/aggregations are configuration problems, not transient query failures:
    the entry is omitted instead of failing the whole period (contract 3.1)."""
    if key not in _unsupported_warned:
        _unsupported_warned.add(key)
        log.warning("Period %s '%s' skipped: not supported by the database (%s: %s)",
                    kind, key, type(error).__name__, error)


def _build_series(series_plan, db_managers, start, end, generated, coverage, running, zone):
    series = {}
    record_indexes = {}
    for key, view_series in series_plan.items():
        manager = db_managers(view_series.binding)
        try:
            if view_series.resolution == NATIVE:
                points, unit, group = native_series(manager, view_series.data_type, start, min(end, generated))
            else:
                grid = buckets(zone, view_series.resolution, start, end)
                if grid:
                    index = _record_index(db_managers, record_indexes, view_series.binding,
                                          grid[0][0], grid[-1][1])
                    points, unit, group = aggregated_series(
                        manager, view_series.data_type, view_series.aggregate_type, view_series.resolution,
                        zone, start, end, generated, coverage.last, running, index)
                else:
                    points, unit, group = [], None, None
        except (weewx.UnknownType, weewx.UnknownAggregation) as e:
            _skip_unsupported('series', key, e)
            continue
        series[key] = {'observation': view_series.obs_key,
                       'aggregate_type': view_series.aggregate_type or 'none',
                       'resolution': view_series.resolution, 'unit': unit, 'group': group, 'points': points}
    return series


def _build_observations(observation_plan, db_managers, start, end, generated, zone):
    observations = {}
    extreme_span = daily_summary_span(zone, start, end)
    for obs_key, observation in observation_plan.items():
        manager = db_managers(observation['data_binding'])
        try:
            unit, group, count, stats, stat_units = observation_stats(
                manager, observation['data_type'], observation['statistics'], start, min(end, generated),
                extreme_span)
        except (weewx.UnknownType, weewx.UnknownAggregation) as e:
            _skip_unsupported('observation', obs_key, e)
            continue
        entry = {'data_binding': observation['data_binding'], 'data_type': observation['data_type'],
                 'unit': unit, 'group': group, 'count': count, 'stats': stats}
        if stat_units:
            entry['stat_units'] = stat_units
        observations[obs_key] = entry
    return observations


def _period_state(running, coverage, gap_threshold):
    if running:
        return 'running'
    missing_percent = (max(0, coverage.expected - coverage.records) * 100.0 / coverage.expected
                       if coverage.expected else 0)
    return 'gaps' if missing_percent > gap_threshold else 'complete'


def build_period_data(db_managers, default_binding, series_plan, observation_plan, zone, kind, period,
                      period_id, span, generated, week_start=None, sun_events=None, fallback_interval=None,
                      gap_threshold=1.0):
    """Assemble a complete period file dict (contract 3).

    db_managers: callable binding -> db_manager.
    span: (start, end) of the calendar period or rolling window; axis = span.
    """
    start, end = int(span[0]), int(span[1])
    generated = int(generated)
    running = kind == 'rolling' or generated < end
    main_manager = db_managers(default_binding)
    coverage = get_coverage(main_manager, start, end, generated, fallback_interval)
    series = _build_series(series_plan, db_managers, start, end, generated, coverage, running, zone)
    observations = _build_observations(observation_plan, db_managers, start, end, generated, zone)
    state = _period_state(running, coverage, gap_threshold)

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
