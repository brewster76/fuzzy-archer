import datetime as dt
import json
import os
import zoneinfo

import pytest

from user import historyperiods as hp
from user import historywriter as hw
from user.historydata import generate_mutable, is_due, resolve_week_start
from user.historyconfig import PeriodChartsConfig

BERLIN = hp.StationZone(zoneinfo.ZoneInfo('Europe/Berlin'), 'Europe/Berlin')
SECTION = {'period_chart_items': ['outTemp'], 'outTemp': {'outTemp': {}}}
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'schemas')


class FakeBuild(object):
    def __init__(self, fail=()):
        self.calls = []
        self.fail = set(fail)

    def __call__(self, db_managers, binding, series, observations, zone, kind, period, period_id, span, now,
                 **kwargs):
        self.calls.append((kind, period, period_id, span))
        if (kind, period) in self.fail:
            raise RuntimeError('db error')
        return {'kind': kind, 'period': period, 'period_id': period_id, 'span': list(span), 'generated': now,
                'series': sorted(series)}


def run(tmp_path, now, build, section=SECTION, week_start=6):
    root = str(tmp_path / 'html' / 'historic_data')
    state = str(tmp_path / 'state')
    config = PeriodChartsConfig(section, 'wx_binding')
    written = generate_mutable(root, state, config, BERLIN, week_start, now, None, 'wx_binding', build=build)
    return root, written


def ts(*args):
    return int(dt.datetime(*args, tzinfo=BERLIN.tzinfo).timestamp())


def test_first_run_writes_everything(tmp_path):
    build = FakeBuild()
    now = ts(2026, 11, 21, 18, 5)
    root, written = run(tmp_path, now, build)
    assert len(written) == 7
    index = hw.read_current_index(root)
    jsonschema = pytest.importorskip('jsonschema')
    with open(os.path.join(SCHEMA_DIR, 'current-v1.schema.json')) as f:
        jsonschema.validate(index, json.load(f))
    assert index['current']['day']['period_id'] == '20261121'
    assert index['current']['week']['period_id'] == '20261115'
    assert index['current']['month']['period_id'] == '202611'
    assert index['current']['day']['refresh'] == 300
    assert index['rolling']['year']['refresh'] == 21600
    rolling_week = hw.read_json(os.path.join(root, 'rolling', 'week.json.gz'))
    assert rolling_week['span'] == [now - 8 * 86400, now]
    assert hw.read_json(os.path.join(root, 'current', 'year.json.gz'))['period_id'] == '2026'


def test_due_logic_across_runs(tmp_path):
    build = FakeBuild()
    now = ts(2026, 11, 21, 18, 5)
    run(tmp_path, now, build)
    build.calls.clear()
    root, written = run(tmp_path, now + 300, build)
    assert written == [('current', 'day')]
    root, written = run(tmp_path, now + 3600 - 20, build)  # within tolerance
    assert set(written) == {('current', 'day'), ('current', 'week'), ('rolling', 'week')}
    index = hw.read_current_index(root)
    assert index['current']['month']['generated'] == now


def test_period_rollover_forces_regeneration(tmp_path):
    build = FakeBuild()
    run(tmp_path, ts(2026, 11, 30, 23, 55), build)
    root, written = run(tmp_path, ts(2026, 12, 1, 0, 0, 1), build)
    assert ('current', 'month') in written and ('current', 'day') in written
    assert ('current', 'year') not in written
    assert hw.read_current_index(root)['current']['month']['period_id'] == '202612'


def test_config_or_week_start_change_forces_all(tmp_path):
    build = FakeBuild()
    now = ts(2026, 11, 21, 18, 5)
    run(tmp_path, now, build)
    _, written = run(tmp_path, now + 300, build, section={'period_chart_items': ['outTemp'],
                                                           'outTemp': {'outTemp': {}, 'dewpoint': {}}})
    assert len(written) == 7
    root, written = run(tmp_path, now + 600, build, section={'period_chart_items': ['outTemp'],
                                                              'outTemp': {'outTemp': {}, 'dewpoint': {}}},
                        week_start=0)
    assert len(written) == 7
    assert hw.read_current_index(root)['current']['week']['period_id'] == '20261116'


def test_failure_keeps_previous_entry_of_same_period_only(tmp_path):
    now = ts(2026, 11, 21, 18, 5)
    run(tmp_path, now, FakeBuild())
    root, written = run(tmp_path, now + 300, FakeBuild(fail={('calendar', 'day')}))
    index = hw.read_current_index(root)
    assert written == [] and index['current']['day']['generated'] == now
    root, _ = run(tmp_path, ts(2026, 11, 22, 0, 5), FakeBuild(fail={('calendar', 'day')}))
    index = hw.read_current_index(root)
    assert 'day' not in index['current'] and index['current']['week']['period_id'] == '20261122'


def test_is_due():
    assert is_due(None, 'x', 3600, 0, False)
    assert is_due({'period_id': 'a', 'generated': 0}, 'b', 3600, 1, False)
    assert not is_due({'period_id': 'a', 'generated': 0}, 'a', 3600, 1000, False)
    assert is_due({'period_id': 'a', 'generated': 0}, 'a', 0, 1, False)
    assert is_due({'period_id': 'a', 'generated': 0}, 'a', 3600, 1, True)


def test_resolve_week_start():
    class Info(object):
        week_start = 0
    assert resolve_week_start({}, Info()) == 0
    assert resolve_week_start({'Station': {'week_start': '2'}}) == 2
    assert resolve_week_start({}) == 6
    with pytest.raises(ValueError):
        resolve_week_start({'Station': {'week_start': '7'}})


def test_integration_with_database(tmp_path):
    """Real build against WeeWX (WEEWX_SRC), reusing the database fixture data generator."""
    pytest.importorskip('configobj')
    pytest.importorskip('weewx')
    import test_historyaggregate as agg
    import weewx.manager
    import weewx.schemas.wview_extended
    path = str(tmp_path / 'weewx.sdb')
    manager = weewx.manager.DaySummaryManager.open_with_create(
        {'driver': 'weedb.sqlite', 'database_name': path}, schema=weewx.schemas.wview_extended.schema)
    try:
        manager.addRecord(agg.make_records())
        now = agg.ZONE.day_start(agg.FIRST_DAY + dt.timedelta(days=8)) + 6 * 3600 + 120
        root = str(tmp_path / 'historic_data')
        config = PeriodChartsConfig(agg.SECTION, 'wx_binding')
        written = generate_mutable(root, str(tmp_path / 'state'), config, agg.ZONE, 6, now,
                                   lambda b: manager, 'wx_binding')
        assert len(written) == 7
        jsonschema = pytest.importorskip('jsonschema')
        with open(os.path.join(SCHEMA_DIR, 'period-v1.schema.json')) as f:
            validator = jsonschema.Draft202012Validator(json.load(f))
        index = hw.read_current_index(root)
        for section in ('current', 'rolling'):
            for period, entry in index[section].items():
                data = hw.read_json(os.path.join(root, *entry['file'].split('/')))
                validator.validate(data)
                assert data['state'] == 'running'
        day = hw.read_json(os.path.join(root, 'current', 'day.json.gz'))
        assert day['coverage']['records'] == 72
    finally:
        manager.close()
