import datetime as dt
import time
import zoneinfo

import pytest

from user import historyperiods as hp

BERLIN = hp.StationZone(zoneinfo.ZoneInfo('Europe/Berlin'), 'Europe/Berlin')
NEW_YORK = hp.StationZone(zoneinfo.ZoneInfo('America/New_York'), 'America/New_York')
SANTIAGO = hp.StationZone(zoneinfo.ZoneInfo('America/Santiago'), 'America/Santiago')


def epoch(zone, *args):
    return int(dt.datetime(*args, tzinfo=zone.tzinfo).timestamp())


def day_length(zone, date):
    start, end = hp.period_span(zone, 'day', date)
    return end - start


@pytest.mark.parametrize('zone,short,long_', [
    (BERLIN, dt.date(2026, 3, 29), dt.date(2026, 10, 25)),
    (NEW_YORK, dt.date(2026, 3, 8), dt.date(2026, 11, 1)),
])
def test_dst_day_lengths(zone, short, long_):
    assert day_length(zone, short) == 23 * 3600
    assert day_length(zone, long_) == 25 * 3600
    assert day_length(zone, dt.date(2026, 6, 1)) == 24 * 3600


def test_hourly_grid_on_dst_days():
    s, e = hp.period_span(BERLIN, 'day', dt.date(2026, 10, 25))
    hours = hp.buckets(BERLIN, 'PT1H', s, e)
    assert len(hours) == 25
    assert all(b - a == 3600 for a, b in hours)
    quarter = hp.buckets(BERLIN, 'PT15M', s, e)
    assert len(quarter) == 100
    s, e = hp.period_span(BERLIN, 'day', dt.date(2026, 3, 29))
    assert len(hp.buckets(BERLIN, 'PT1H', s, e)) == 23
    # local 02:00 does not exist and is skipped: 00:00 -> 04:00 local lasts 3 real hours
    two_hours = hp.buckets(BERLIN, 'PT2H', s, e)
    assert [b - a for a, b in two_hours][:2] == [10800, 7200]


def test_fall_back_repeated_boundaries_are_distinct():
    naive = dt.datetime(2026, 10, 25, 2, 0)
    epochs = BERLIN.epochs(naive)
    assert len(epochs) == 2
    assert epochs[1] - epochs[0] == 3600
    assert BERLIN.epochs(dt.datetime(2026, 3, 29, 2, 30)) == []


def test_santiago_midnight_gap():
    found = []
    date = dt.date(2026, 1, 1)
    while date.year == 2026:
        start = SANTIAGO.day_start(date)
        local = SANTIAGO.local(start)
        if local.time() != dt.time(0, 0):
            found.append(date)
            assert local.date() == date
            assert local.time() == dt.time(1, 0)
            assert day_length(SANTIAGO, date) == 23 * 3600
            assert SANTIAGO.local(start - 1).date() == date - dt.timedelta(days=1)
            p1d = hp.buckets(SANTIAGO, 'P1D', start, start + 3600)
            assert p1d[0] == (start, start + 23 * 3600)
        date += dt.timedelta(days=1)
    assert found, "expected a day whose midnight does not exist"


@pytest.mark.parametrize('week_start,expected', [(6, '20251228'), (0, '20251229'), (2, '20251231')])
def test_week_start(week_start, expected):
    start = hp.period_start_date('week', dt.date(2026, 1, 1), week_start)
    assert hp.period_id('week', start) == expected
    assert hp.parse_period_id('week', expected, week_start) == start
    s, e = hp.period_span(BERLIN, 'week', start)
    assert e - s == 7 * 86400


def test_parse_period_id_validation():
    assert hp.parse_period_id('month', '202402') == dt.date(2024, 2, 1)
    for period, pid in [('day', '2026011'), ('day', '../x'), ('month', '202613'), ('year', '20xx'),
                        ('day', '20260230')]:
        with pytest.raises(ValueError):
            hp.parse_period_id(period, pid)
    with pytest.raises(ValueError):
        hp.parse_period_id('week', '20260101', 6)  # Thursday


def test_leap_year_spans():
    s, e = hp.period_span(BERLIN, 'month', dt.date(2024, 2, 1))
    assert e - s == 29 * 86400
    s, e = hp.period_span(BERLIN, 'year', dt.date(2024, 1, 1))
    assert e - s == 366 * 86400
    assert hp.next_period_date('year', dt.date(2024, 1, 1)) == dt.date(2025, 1, 1)
    assert hp.next_period_date('month', dt.date(2024, 12, 1)) == dt.date(2025, 1, 1)


def test_edge_bucket_full_span():
    start = epoch(BERLIN, 2026, 6, 15, 10, 7)
    end = start + 8 * 86400
    grid = hp.buckets(BERLIN, 'PT15M', start, end)
    assert grid[0] == (epoch(BERLIN, 2026, 6, 15, 10, 0), epoch(BERLIN, 2026, 6, 15, 10, 15))
    assert grid[-1][0] < end <= grid[-1][1]


def test_record_at_midnight_belongs_to_previous_day():
    midnight = epoch(BERLIN, 2026, 6, 16)
    assert hp.period_of_record(BERLIN, 'day', midnight, 6) == dt.date(2026, 6, 15)
    assert hp.period_of_record(BERLIN, 'day', midnight + 1, 6) == dt.date(2026, 6, 16)
    assert hp.current_period(BERLIN, 'day', midnight, 6) == dt.date(2026, 6, 16)
    assert hp.period_of_record(BERLIN, 'year', epoch(BERLIN, 2026, 1, 1), 6) == dt.date(2025, 1, 1)


def test_rolling_window():
    now = epoch(BERLIN, 2026, 10, 28, 12, 34)
    for period, days in [('week', 8), ('month', 32), ('year', 367)]:
        s, e = hp.rolling_window(period, now)
        assert e == now
        assert e - s == days * 86400
    with pytest.raises(ValueError):
        hp.rolling_window('day', now)


def test_normalize_resolution():
    assert hp.normalize_resolution(900) == 'PT15M'
    assert hp.normalize_resolution('86400') == 'P1D'
    assert hp.normalize_resolution('Native') == 'native'
    assert hp.normalize_resolution('pt1h') == 'PT1H'
    for bad in ('700', 'PT7M', 'abc'):
        with pytest.raises(ValueError):
            hp.normalize_resolution(bad)


def test_transitions():
    s, e = hp.period_span(BERLIN, 'day', dt.date(2026, 10, 25))
    tr = BERLIN.transitions(s, e)
    assert tr == [[s, 7200], [epoch(BERLIN, 2026, 10, 25, 1) + 2 * 3600, 3600]]
    s, e = hp.period_span(BERLIN, 'day', dt.date(2026, 6, 1))
    assert BERLIN.transitions(s, e) == [[s, 7200]]


def test_iter_periods_newest_first():
    dates = list(hp.iter_periods('month', dt.date(2025, 11, 20), dt.date(2026, 2, 3), 6, newest_first=True))
    assert dates == [dt.date(2026, 2, 1), dt.date(2026, 1, 1), dt.date(2025, 12, 1), dt.date(2025, 11, 1)]


def test_host_local_zone_without_name():
    zone = hp.StationZone(None, None)
    date = dt.date(2026, 6, 15)
    assert zone.day_start(date) == int(time.mktime((2026, 6, 15, 0, 0, 0, 0, 0, -1)))
    s, e = hp.period_span(zone, 'day', date)
    assert len(hp.buckets(zone, 'PT1H', s, e)) == (e - s) // 3600
