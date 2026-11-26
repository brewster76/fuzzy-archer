"""Approximated sun events (used when skyfield is not installed)."""
import calendar

import pytest

from user import sunevents
from user.sunevents import ApproxSunEvents, compute_sun_events

VIENNA = (16.37, 48.21)


def utc(*args):
    return calendar.timegm(args + (0,) * (6 - len(args)))


def by_type(events, kind):
    return [e for e in events if e[2] == kind]


def test_summer_solstice_vienna():
    start, end = utc(2026, 6, 21), utc(2026, 6, 22)
    events = ApproxSunEvents(start, end, *VIENNA).get_transits(6)
    assert events[0][2] == 'start'
    assert events[-1][2] == 'end'
    assert [e[0] for e in events] == sorted(e[0] for e in events)
    [transit] = by_type(events, 'transit')
    # local mean noon 10:54:31 UTC, equation of time about -1.8 min
    assert abs(transit[0] - utc(2026, 6, 21, 10, 56, 20)) < 60
    assert transit[1] == 65  # 90 - 48.21 + 23.44
    [antitransit] = by_type(events, 'antitransit')
    assert antitransit[1] == -18
    risings = by_type(events, 'rising')
    settings = by_type(events, 'setting')
    assert [e[1] for e in risings] == [-6, 6]
    assert [e[1] for e in settings] == [6, -6]
    # geometric sunrise of the center about 03:01 UTC
    assert risings[0][0] < utc(2026, 6, 21, 3, 1) < risings[1][0]


def test_equinox_day_length():
    start, end = utc(2026, 3, 20), utc(2026, 3, 21)
    events = ApproxSunEvents(start, end, 0.0, 0.0).get_transits(0)
    [rising] = by_type(events, 'rising')
    [setting] = by_type(events, 'setting')
    assert abs((setting[0] - rising[0]) - 12 * 3600) < 120


def test_polar_day_has_no_rising_or_setting():
    events = ApproxSunEvents(utc(2026, 6, 20), utc(2026, 6, 23), 15.6, 78.2).get_transits(6)
    assert not by_type(events, 'rising')
    assert not by_type(events, 'setting')
    assert len(by_type(events, 'transit')) == 3
    assert all(e[1] > 6 for e in events)


def test_week_span_events_are_inside_the_range():
    start, end = utc(2026, 11, 23, 13, 7), utc(2026, 11, 30, 13, 7)
    events = ApproxSunEvents(start, end, *VIENNA).get_transits(6)
    assert all(start <= e[0] <= end for e in events)
    assert len(by_type(events, 'transit')) == 7
    assert len(by_type(events, 'rising')) == 14


def test_falls_back_without_skyfield(monkeypatch, tmp_path):
    monkeypatch.setattr(sunevents, 'api', None)
    start, end = utc(2026, 6, 21), utc(2026, 6, 22)
    events = compute_sun_events(start, end, VIENNA[0], VIENNA[1], 170, str(tmp_path / 'skyfield'), 'de440s.bsp', 6)
    assert events == ApproxSunEvents(start, end, *VIENNA).get_transits(6)
    assert not (tmp_path / 'skyfield').exists()


def test_falls_back_when_skyfield_fails(monkeypatch, tmp_path):
    class Broken(object):
        def __init__(self, *args):
            raise IOError('ephemeris download failed')

    monkeypatch.setattr(sunevents, 'api', object())
    monkeypatch.setattr(sunevents, 'SunEvents', Broken)
    start, end = utc(2026, 6, 21), utc(2026, 6, 22)
    events = compute_sun_events(start, end, VIENNA[0], VIENNA[1], 170, str(tmp_path), 'de440s.bsp', 6)
    assert events == ApproxSunEvents(start, end, *VIENNA).get_transits(6)


@pytest.mark.parametrize('angle', [0, 6])
def test_angle_zero_has_single_crossings(angle):
    events = ApproxSunEvents(utc(2026, 6, 21), utc(2026, 6, 22), *VIENNA).get_transits(angle)
    assert len(by_type(events, 'rising')) == (1 if angle == 0 else 2)
