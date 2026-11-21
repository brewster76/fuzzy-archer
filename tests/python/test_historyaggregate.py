"""Integration tests of historyaggregate against a real WeeWX 5.5.x database (set WEEWX_SRC)."""
import datetime as dt
import json
import os

import pytest

pytest.importorskip('configobj')
weewx = pytest.importorskip('weewx')
import weewx.manager  # noqa: E402
import weewx.schemas.wview_extended  # noqa: E402

from user import historyperiods as hp  # noqa: E402
from user.historyaggregate import build_period_data  # noqa: E402
from user.historyconfig import PeriodChartsConfig  # noqa: E402

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'schemas')
ZONE = hp.StationZone(None, None)  # host local time, consistent with WeeWX daily summaries
FIRST_DAY = dt.date(2026, 6, 14)
DAYS = 10

SECTION = {
    'period_chart_items': ['outTemp', 'rain', 'windDir'],
    'outTemp': {'outTemp': {}},
    'rain': {'rain': {'plotType': 'bar', 'aggregateType': 'sum', 'aggregateInterval': '1800',
                      'week': {'aggregateInterval': 'P1D'}}},
    'windDir': {'windDir': {}},
}


def make_records():
    start = ZONE.day_start(FIRST_DAY)
    end = ZONE.day_start(FIRST_DAY + dt.timedelta(days=DAYS))
    for i, ts in enumerate(range(start + 300, end + 1, 300)):
        yield {'dateTime': ts, 'usUnits': weewx.US, 'interval': 5,
               'outTemp': 50.0 + (i % 288) / 10.0,
               'rain': 0.01 if (i % 288) < 12 else 0.0,
               'windSpeed': 5.0, 'windGust': 7.0,
               'windDir': 80.0 if i % 2 else 100.0}


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    path = str(tmp_path_factory.mktemp('db') / 'weewx.sdb')
    manager = weewx.manager.DaySummaryManager.open_with_create(
        {'driver': 'weedb.sqlite', 'database_name': path}, schema=weewx.schemas.wview_extended.schema)
    manager.addRecord(make_records())
    # archive gap: 3 records missing on day 3
    gap_day_start = ZONE.day_start(FIRST_DAY + dt.timedelta(days=2))
    for k in (100, 101, 102):
        manager.getSql("DELETE FROM archive WHERE dateTime = ?", (gap_day_start + 300 * k,))
    yield manager
    manager.close()


@pytest.fixture(scope='module')
def schema_validator():
    jsonschema = pytest.importorskip('jsonschema')
    with open(os.path.join(SCHEMA_DIR, 'period-v1.schema.json')) as f:
        schema = json.load(f)
    return jsonschema.Draft202012Validator(schema)


def build(db, view, kind, span, generated, period_id=None, sun_events=None, gap_threshold=1.0):
    config = PeriodChartsConfig(SECTION, 'wx_binding')
    series, observations = config.view_plan(view)
    data = build_period_data(lambda binding: db, 'wx_binding', series, observations, ZONE, kind, view,
                             period_id, span, generated, week_start=6, sun_events=sun_events,
                             fallback_interval=300, gap_threshold=gap_threshold)
    return json.loads(json.dumps(data, allow_nan=False))


def test_complete_day(db, schema_validator):
    day = FIRST_DAY + dt.timedelta(days=1)
    span = hp.period_span(ZONE, 'day', day)
    data = build(db, 'day', 'calendar', span, span[1] + 3600, hp.period_id('day', day),
                 sun_events=lambda s, e: [[s, 1.0, 'start'], [e, 1.0, 'end']])
    schema_validator.validate(data)
    assert data['state'] == 'complete'
    assert data['coverage'] == {'first': span[0] + 300, 'last': span[1], 'records': 288,
                                'expected': 288, 'archive_interval': 300}
    temp = data['series']['wx_binding/outTemp/none/native']
    assert len(temp['points']) == 288 and temp['unit'] == 'degree_F'
    assert temp['points'][0] == [span[0], span[0] + 300, 50.0]
    rain = data['series']['wx_binding/rain/sum/PT30M']['points']
    assert len(rain) == 48 and rain[0][2] == pytest.approx(0.06) and rain[2][2] == 0
    stats = data['observations']['wx_binding/outTemp']['stats']
    assert stats['min'] == [50.0, span[0] + 300] and stats['max'] == [78.7, span[1]]
    wind = data['observations']['wx_binding/windDir']
    assert wind['stats']['vecdir'] == pytest.approx(90.0, abs=0.01)
    assert wind['stat_units']['vecavg'][1] == 'group_speed'
    assert data['observations']['wx_binding/rain']['stats']['sum'] == pytest.approx(0.12)
    assert data['sun_events'] == [[span[0], 1.0, 'start'], [span[1], 1.0, 'end']]


def test_gaps_state(db, schema_validator):
    day = FIRST_DAY + dt.timedelta(days=2)
    span = hp.period_span(ZONE, 'day', day)
    data = build(db, 'day', 'calendar', span, span[1] + 60, hp.period_id('day', day))
    schema_validator.validate(data)
    assert data['state'] == 'gaps'
    assert data['coverage']['records'] == 285 and data['coverage']['expected'] == 288


def test_gap_threshold_is_a_percentage(db):
    day = FIRST_DAY + dt.timedelta(days=2)
    span = hp.period_span(ZONE, 'day', day)
    period_id = hp.period_id('day', day)
    tolerated = build(db, 'day', 'calendar', span, span[1] + 60, period_id, gap_threshold=1.1)
    exceeded = build(db, 'day', 'calendar', span, span[1] + 60, period_id, gap_threshold=1.0)
    assert tolerated['state'] == 'complete'
    assert exceeded['state'] == 'gaps'


def test_running_day_provisional_buckets(db, schema_validator):
    day = FIRST_DAY + dt.timedelta(days=4)
    span = hp.period_span(ZONE, 'day', day)
    now = span[0] + 12 * 3600 + 420  # 12:07, last record 12:05
    data = build(db, 'day', 'calendar', span, now, hp.period_id('day', day))
    schema_validator.validate(data)
    assert data['state'] == 'running'
    assert data['coverage']['last'] == span[0] + 12 * 3600 + 300
    assert len(data['series']['wx_binding/outTemp/none/native']['points']) == 145
    rain = data['series']['wx_binding/rain/sum/PT30M']['points']
    assert len(rain) == 48
    assert len(rain[23]) == 3 and len(rain[24]) == 4  # 11:30-12:00 final, 12:00-12:30 provisional
    assert rain[24][2] == 0 and rain[25] == [rain[25][0], rain[25][1], None, 1]


def test_week_daily_sums_match_daily_totals(db, schema_validator):
    week_start = hp.period_start_date('week', FIRST_DAY + dt.timedelta(days=3), 6)
    span = hp.period_span(ZONE, 'week', week_start)
    data = build(db, 'week', 'calendar', span, span[1] + 60, hp.period_id('week', week_start))
    schema_validator.validate(data)
    rain = data['series']['wx_binding/rain/sum/P1D']['points']
    assert len(rain) == 7
    assert all(p[2] == pytest.approx(0.12) for p in rain if p[0] >= ZONE.day_start(FIRST_DAY))
    wind = data['series']['wx_binding/wind/vecdir/PT15M']
    assert wind['group'] == 'group_direction'
    assert all(p[2] is None or 80.0 < p[2] < 100.0 for p in wind['points'])
    assert data['week_start'] == 6


def test_rolling_week_edge_bucket(db, schema_validator):
    now = ZONE.day_start(FIRST_DAY + dt.timedelta(days=9)) + 10 * 3600 + 7 * 60
    span = hp.rolling_window('week', now)
    data = build(db, 'week', 'rolling', span, now)
    schema_validator.validate(data)
    temp = data['series']['wx_binding/outTemp/avg/PT15M']['points']
    first = temp[0]
    assert first[0] == span[0] - 7 * 60 and first[1] == span[0] + 8 * 60
    # full nominal span (10:00, 10:15]: records 10:05, 10:10, 10:15 -> i%288 = 120..122
    assert first[2] == pytest.approx(50.0 + 12.1)
    assert data['period_id'] is None and data['state'] == 'running'
    assert data['sun_events'] == []
