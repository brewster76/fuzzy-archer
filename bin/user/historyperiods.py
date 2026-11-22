# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Calendar periods, rolling windows and fixed local aggregation grids for the period views.

Pure logic without WeeWX dependencies. All timestamps are Unix epoch seconds (int).
Spans are half-open on the left, (start, end], like WeeWX archive record selection.
See docs/historic-data-contract.md, section 1.
"""

import datetime as dt
import logging
import re

log = logging.getLogger(__name__)

PERIODS = ('day', 'week', 'month', 'year')
ROLLING_PERIODS = ('week', 'month', 'year')
ROLLING_DAYS = {'week': 8, 'month': 32, 'year': 367}
NATIVE = 'native'

# resolution code -> step in minutes (sub-daily, wall clock) or None (native / calendar day)
RESOLUTION_MINUTES = {
    'PT5M': 5,
    'PT10M': 10,
    'PT15M': 15,
    'PT30M': 30,
    'PT1H': 60,
    'PT2H': 120,
    'PT3H': 180,
    'PT6H': 360,
}
CALENDAR_DAY = 'P1D'
RESOLUTIONS = (NATIVE,) + tuple(RESOLUTION_MINUTES) + (CALENDAR_DAY,)
SECONDS_TO_RESOLUTION = {minutes * 60: code for code, minutes in RESOLUTION_MINUTES.items()}
SECONDS_TO_RESOLUTION[86400] = CALENDAR_DAY

_PERIOD_ID_PATTERNS = {
    'day': re.compile(r'^\d{8}$'),
    'week': re.compile(r'^\d{8}$'),
    'month': re.compile(r'^\d{6}$'),
    'year': re.compile(r'^\d{4}$'),
}
_PERIOD_ID_FORMATS = {'day': '%Y%m%d', 'week': '%Y%m%d', 'month': '%Y%m', 'year': '%Y'}
UNKNOWN_PERIOD_ERROR = "Unknown period '%s'"


def normalize_resolution(value):
    """Return the resolution code for a code or an equivalent number of seconds."""
    text = str(value).strip()
    if text.lower() == NATIVE:
        return NATIVE
    if text.upper() in RESOLUTIONS:
        return text.upper()
    try:
        seconds = int(text)
    except ValueError:
        raise ValueError("Unsupported resolution '%s'" % value)
    if seconds in SECONDS_TO_RESOLUTION:
        return SECONDS_TO_RESOLUTION[seconds]
    raise ValueError("Unsupported resolution '%s' seconds" % value)


class StationZone(object):
    """Station time zone: an IANA zone (zoneinfo) or, if unavailable, the process local time.

    The process local time is what WeeWX uses for its own calendar computations; an IANA zone is
    preferred because it can be passed to the frontend.
    """

    def __init__(self, tzinfo=None, name=None):
        self.tzinfo = tzinfo
        self.name = name

    @classmethod
    def detect(cls):
        name = None
        try:
            from tzlocal import get_localzone_name
            name = get_localzone_name()
        except Exception as e:
            log.warning("Could not determine IANA time zone name of the host (%s). "
                        "Using host local time without zone name.", e)
        if name:
            try:
                import zoneinfo
                return cls(zoneinfo.ZoneInfo(name), name)
            except Exception as e:
                log.warning("Time zone '%s' not available in zoneinfo (%s). "
                            "Using host local time.", name, e)
        return cls(None, None)

    def local(self, ts):
        """Local datetime of an epoch (aware for zoneinfo, naive with correct fold otherwise)."""
        return dt.datetime.fromtimestamp(ts, self.tzinfo)

    def utcoffset(self, ts):
        local = self.local(ts)
        if self.tzinfo is None:
            local = local.astimezone()
        return int(local.utcoffset().total_seconds())

    def _raw_epoch(self, naive, fold):
        return int(naive.replace(fold=fold, tzinfo=self.tzinfo).timestamp())

    def _wall(self, ts):
        return self.local(ts).replace(tzinfo=None, fold=0)

    def epochs(self, naive):
        """All epochs at which the local wall clock shows `naive`: [] (DST gap), 1 or 2 (DST overlap)."""
        naive = naive.replace(tzinfo=None, fold=0)
        result = set()
        for fold in (0, 1):
            ts = self._raw_epoch(naive, fold)
            if self._wall(ts) == naive:
                result.add(ts)
        return sorted(result)

    def day_start(self, date):
        """First instant of a local date: local 00:00, or the end of a DST gap covering 00:00."""
        midnight = dt.datetime.combine(date, dt.time())
        valid = self.epochs(midnight)
        if valid:
            return valid[0]
        lo, hi = sorted((self._raw_epoch(midnight, 1), self._raw_epoch(midnight, 0)))
        if lo == hi:
            lo -= 7200
        # predicate "local date >= date" is False at lo and True at hi inside a gap
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.local(mid).date() >= date:
                hi = mid
            else:
                lo = mid
        return hi

    def transitions(self, start, end, step=3600):
        """[[epoch, utc_offset_seconds], ...]: offset at start and every offset change in (start, end]."""
        result = [[int(start), self.utcoffset(start)]]
        previous = result[0][1]
        t = int(start)
        while t < end:
            nt = min(t + step, int(end))
            offset = self.utcoffset(nt)
            if offset != previous:
                lo, hi = t, nt
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if self.utcoffset(mid) == previous:
                        lo = mid
                    else:
                        hi = mid
                result.append([hi, offset])
                previous = offset
            t = nt
        return result


# ---------------------------------------------------------------------------------------------
# Calendar periods
# ---------------------------------------------------------------------------------------------

def period_start_date(period, date, week_start):
    """Local start date of the calendar period containing local `date`.

    week_start uses the WeeWX encoding (0 = Monday ... 6 = Sunday), same as date.weekday().
    """
    if period == 'day':
        return date
    if period == 'week':
        return date - dt.timedelta(days=(date.weekday() - int(week_start)) % 7)
    if period == 'month':
        return date.replace(day=1)
    if period == 'year':
        return date.replace(month=1, day=1)
    raise ValueError(UNKNOWN_PERIOD_ERROR % period)


def next_period_date(period, start_date):
    if period == 'day':
        return start_date + dt.timedelta(days=1)
    if period == 'week':
        return start_date + dt.timedelta(days=7)
    if period == 'month':
        if start_date.month == 12:
            return start_date.replace(year=start_date.year + 1, month=1)
        return start_date.replace(month=start_date.month + 1)
    if period == 'year':
        return start_date.replace(year=start_date.year + 1)
    raise ValueError(UNKNOWN_PERIOD_ERROR % period)


def previous_period_date(period, start_date, week_start):
    return period_start_date(period, start_date - dt.timedelta(days=1), week_start)


def period_span(zone, period, start_date):
    """(start, end) epochs of the calendar period beginning at local `start_date`."""
    return zone.day_start(start_date), zone.day_start(next_period_date(period, start_date))


def period_id(period, start_date):
    return start_date.strftime(_PERIOD_ID_FORMATS[period])


def parse_period_id(period, pid, week_start=None):
    """Validate a period id and return its local start date. Raises ValueError."""
    if period not in _PERIOD_ID_PATTERNS:
        raise ValueError(UNKNOWN_PERIOD_ERROR % period)
    if not isinstance(pid, str) or not _PERIOD_ID_PATTERNS[period].match(pid):
        raise ValueError("Invalid %s id '%s'" % (period, pid))
    if period == 'year':
        date = dt.date(int(pid), 1, 1)
    elif period == 'month':
        date = dt.date(int(pid[:4]), int(pid[4:6]), 1)
    else:
        date = dt.date(int(pid[:4]), int(pid[4:6]), int(pid[6:8]))
    if period == 'week' and week_start is not None and period_start_date('week', date, week_start) != date:
        raise ValueError("'%s' is not a week start for week_start=%s" % (pid, week_start))
    return date


def _adjust(zone, period, start_date, week_start, contains):
    """Move start_date until contains(start, end) is true (handles DST edge cases at midnight)."""
    for _ in range(3):
        start, end = period_span(zone, period, start_date)
        position = contains(start, end)
        if position == 0:
            return start_date
        if position > 0:
            start_date = next_period_date(period, start_date)
        else:
            start_date = previous_period_date(period, start_date, week_start)
    return start_date


def current_period(zone, period, now, week_start):
    """Start date of the calendar period running at `now` (start <= now < end)."""
    candidate = period_start_date(period, zone.local(now).date(), week_start)
    return _adjust(zone, period, candidate, week_start, lambda s, e: _position_current(s, e, now))


def _position_current(start, end, now):
    if start <= now < end:
        return 0
    return 1 if now >= end else -1


def period_of_record(zone, period, ts, week_start):
    """Start date of the calendar period an archive record with timestamp ts belongs to (start < ts <= end)."""
    candidate = period_start_date(period, zone.local(ts - 1).date(), week_start)
    return _adjust(zone, period, candidate, week_start, lambda s, e: _position_record(s, e, ts))


def _position_record(start, end, timestamp):
    if start < timestamp <= end:
        return 0
    return 1 if timestamp > end else -1


def iter_periods(period, first_date, last_date, week_start, newest_first=False):
    """Start dates of all calendar periods between the periods containing first_date and last_date."""
    first = period_start_date(period, first_date, week_start)
    last = period_start_date(period, last_date, week_start)
    if newest_first:
        date = last
        while date >= first:
            yield date
            date = previous_period_date(period, date, week_start)
    else:
        date = first
        while date <= last:
            yield date
            date = next_period_date(period, date)


def rolling_window(period, now):
    """(start, end) of a rolling window: exactly N * 86400 seconds ending at now."""
    if period not in ROLLING_DAYS:
        raise ValueError("No rolling window for period '%s'" % period)
    now = int(now)
    return now - ROLLING_DAYS[period] * 86400, now


# ---------------------------------------------------------------------------------------------
# Aggregation grids
# ---------------------------------------------------------------------------------------------

def grid_boundaries(zone, resolution, start, end):
    """Fixed local grid boundaries covering [start, end].

    Includes the last boundary <= start and the first boundary >= end. Non-existent local times
    are skipped, repeated local times (DST fall-back) yield two boundaries.
    """
    if resolution == NATIVE:
        raise ValueError("native resolution has no grid")
    first_date = zone.local(start).date() - dt.timedelta(days=1)
    last_date = zone.local(end).date() + dt.timedelta(days=1)
    boundaries = set()
    date = first_date
    if resolution == CALENDAR_DAY:
        while date <= last_date:
            boundaries.add(zone.day_start(date))
            date += dt.timedelta(days=1)
    else:
        try:
            step = RESOLUTION_MINUTES[resolution]
        except KeyError:
            raise ValueError("Unsupported resolution '%s'" % resolution)
        while date <= last_date:
            midnight = dt.datetime.combine(date, dt.time())
            for minute in range(0, 1440, step):
                boundaries.update(zone.epochs(midnight + dt.timedelta(minutes=minute)))
            date += dt.timedelta(days=1)
    ordered = sorted(boundaries)
    first_index = max(i for i, b in enumerate(ordered) if b <= start)
    last_index = min(i for i, b in enumerate(ordered) if b >= end)
    return ordered[first_index:last_index + 1]


def buckets(zone, resolution, axis_start, axis_end):
    """All full nominal grid intervals (start, end] that intersect the axis range (axis_start, axis_end]."""
    bounds = grid_boundaries(zone, resolution, axis_start, axis_end)
    return [(a, b) for a, b in zip(bounds, bounds[1:]) if b > axis_start and a < axis_end]
