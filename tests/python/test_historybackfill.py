import datetime as dt
import json
import os
import sqlite3
import zoneinfo

import pytest

from user import historyperiods as hp
from user import historywriter as hw
from user.historybackfill import Backfill, needs_run
from user.historyconfig import PeriodChartsConfig

BERLIN = hp.StationZone(zoneinfo.ZoneInfo('Europe/Berlin'), 'Europe/Berlin')
SECTION = {'period_chart_items': ['outTemp'], 'outTemp': {'outTemp': {}}, 'backfill_pause': '0'}
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'schemas')


def ts(*args):
    return int(dt.datetime(*args, tzinfo=BERLIN.tzinfo).timestamp())


class FakeDB(object):
    table_name = 'archive'

    def __init__(self, start, end, step=3600, skip=()):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('CREATE TABLE archive (dateTime INTEGER PRIMARY KEY)')
        self.conn.executemany('INSERT INTO archive VALUES (?)',
                              [(t,) for t in range(start + step, end + 1, step) if not any(a < t <= b for a, b in skip)])

    def getSql(self, sql, args=()):
        return self.conn.execute(sql, args).fetchone()


class FakeBuild(object):
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail or (lambda period, pid: False)

    def __call__(self, db_managers, binding, series, observations, zone, kind, period, period_id, span, now, **kw):
        self.calls.append((period, period_id))
        if self.fail(period, period_id):
            raise RuntimeError('boom')
        return {'schema_version': 1, 'kind': 'calendar', 'period': period, 'period_id': period_id,
                'state': 'complete', 'week_start': kw.get('week_start'),
                'observations': {'wx_binding/outTemp': {'count': 1}}}


class Clock(object):
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def make(tmp_path, db, now, build=None, week_start=6, section=SECTION):
    config = PeriodChartsConfig(section, 'wx_binding')
    root = str(tmp_path / 'historic_data')
    state = str(tmp_path / 'state')
    return Backfill(root, state, config, BERLIN, week_start, lambda b: db, 'wx_binding',
                    build=build or FakeBuild(), clock=Clock(now), sleep=lambda s: None)


def test_tasks_newest_first_and_completion(tmp_path):
    first, last = ts(2026, 10, 30, 12), ts(2026, 11, 21, 18)
    worker = make(tmp_path, None, last + 60)
    tasks, next_check = worker.tasks(first, last, last + 60)
    ids = [(p, hp.period_id(p, d)) for p, d, _ in tasks]
    assert ids[0] == ('day', '20261120')
    assert ('month', '202610') in ids
    assert ('week', '20261025') in ids
    assert ('day', '20261030') in ids
    assert ('day', '20261101') in ids
    assert ids.index(('day', '20261030')) > ids.index(('day', '20261101'))
    assert not any(p == 'year' for p, _ in ids)
    assert ('month', '202611') not in ids
    assert ('day', '20261121') not in ids
    assert next_check == ts(2026, 11, 22)
    # just after midnight, before the midnight record is in the archive: day waits for grace or record
    tasks, next_check = worker.tasks(first, ts(2026, 11, 21, 23, 55), ts(2026, 11, 22, 0, 0, 30))
    assert ('day', '20261121') not in [(p, hp.period_id(p, d)) for p, d, _ in tasks]
    assert next_check == ts(2026, 11, 22) + 3600
    tasks, _ = worker.tasks(first, ts(2026, 11, 22), ts(2026, 11, 22, 0, 0, 30))
    assert tasks[0][0] == 'day'
    assert hp.period_id('day', tasks[0][1]) == '20261121'


def test_run_resume_and_manifest(tmp_path):
    first, now = ts(2026, 11, 1), ts(2026, 11, 21, 18)
    db = FakeDB(first, now - 3600, skip=[(ts(2026, 11, 10), ts(2026, 11, 11))])
    build = FakeBuild()
    worker = make(tmp_path, db, now, build)
    state = worker.run()
    assert state['state'] == 'done'
    assert state['next_check'] == ts(2026, 11, 22)
    m = hw.Manifest(worker.root, 6)
    assert m.get('day', '20261110') == {'s': 'nodata'}
    assert m.get('day', '20261120')['s'] == 'ok'
    assert m.get('week', '20261101')['s'] == 'ok'
    assert m.get('week', '20261025') is None  # ends exactly at the archive start
    assert m.get('month', '202610') is None  # month before the archive start
    assert m.index['backfill']['state'] == 'done'
    assert m.index['backfill']['done'] == m.index['backfill']['total']
    assert ('day', '20261110') not in build.calls
    jsonschema = pytest.importorskip('jsonschema')
    with open(os.path.join(SCHEMA_DIR, 'manifest-v1.schema.json')) as f:
        schema = json.load(f)
    jsonschema.validate(hw.read_json(os.path.join(worker.root, 'manifest.json')), schema)
    jsonschema.validate(hw.read_json(os.path.join(worker.root, 'manifest', 'day', '2026.json')), schema)
    # second run: nothing to do
    build2 = FakeBuild()
    make(tmp_path, db, now + 300, build2).run()
    assert build2.calls == []
    # next day: only the new day
    db.conn.executemany('INSERT INTO archive VALUES (?)', [(t,) for t in range(now, ts(2026, 11, 22, 1), 3600)])
    build3 = FakeBuild()
    make(tmp_path, db, ts(2026, 11, 22, 1), build3).run()
    assert set(build3.calls) == {('day', '20261121'), ('week', '20261115')}  # Sunday: week completed too


def test_retry_backoff_and_error(tmp_path):
    first, now = ts(2026, 11, 18), ts(2026, 11, 21, 18)
    db = FakeDB(first, now)
    fail = lambda period, pid: pid == '20261119'
    worker = make(tmp_path, db, now, FakeBuild(fail))
    state = worker.run()
    assert state['state'] == 'idle'
    assert state['next_check'] == now + 600
    assert hw.Manifest(worker.root, 6).get('day', '20261119') is None
    assert make(tmp_path, db, now + 300, FakeBuild(fail)).run()['next_check'] == now + 600
    make(tmp_path, db, now + 600, FakeBuild(fail)).run()
    state = make(tmp_path, db, now + 600 + 1200, FakeBuild(fail)).run()
    assert hw.Manifest(worker.root, 6).get('day', '20261119') == {'s': 'error', 'tries': 3}
    assert state['state'] == 'done'


def test_week_start_change_marks_incompatible(tmp_path):
    first, now = ts(2026, 11, 1), ts(2026, 11, 21, 18)
    db = FakeDB(first, now)
    make(tmp_path, db, now, week_start=6).run()
    build = FakeBuild()
    worker = make(tmp_path, db, now + 300, build, week_start=0)
    worker.run()
    weeks = hw.Manifest(worker.root, 0).entries('week')
    assert weeks
    assert all(e == {'s': 'incompatible'} for e in weeks.values())
    assert not any(p == 'week' for p, _ in build.calls)


def test_needs_run(tmp_path):
    d = str(tmp_path)
    assert needs_run(d, 'h', 0)
    hw.write_json(os.path.join(d, 'worker.json'), {'config': 'h', 'state': 'done', 'next_check': 100})
    assert not needs_run(d, 'h', 99)
    assert needs_run(d, 'h', 100)
    assert needs_run(d, 'other', 0)


WEEWX_CONF = """
WEEWX_ROOT = {root}
[Station]
    location = Test
    latitude = 50.0
    longitude = 8.0
    altitude = 100, meter
    station_type = Simulator
    week_start = 6
[StdArchive]
    archive_interval = 300
[DataBindings]
    [[wx_binding]]
        database = archive_sqlite
        table_name = archive
        manager = weewx.manager.DaySummaryManager
        schema = weewx.schemas.wview_extended.schema
[Databases]
    [[archive_sqlite]]
        database_name = weewx.sdb
        database_type = SQLite
[DatabaseTypes]
    [[SQLite]]
        driver = weedb.sqlite
        SQLITE_ROOT = %(WEEWX_ROOT)s/archive
"""


def test_worker_main_end_to_end(tmp_path, monkeypatch):
    pytest.importorskip('configobj')
    pytest.importorskip('weewx')
    import test_historyaggregate as agg
    import weewx.manager
    import weeutil.logger
    from user import historybackfill
    if not hasattr(__import__('socket'), 'AF_UNIX'):
        monkeypatch.setattr(weeutil.logger, 'setup', lambda *args, **kw: None)
    weewx_root = tmp_path / 'weewx'
    (weewx_root / 'archive').mkdir(parents=True)
    conf = weewx_root / 'weewx.conf'
    conf.write_text(WEEWX_CONF.format(root=str(weewx_root).replace('\\', '/')))
    import configobj
    binder = weewx.manager.DBBinder(configobj.ConfigObj(str(conf)))
    binder.get_manager('wx_binding', initialize=True).addRecord(agg.make_records())
    binder.close()
    root = str(tmp_path / 'html' / 'historic_data')
    state_dir = hw.state_dir({'WEEWX_ROOT': str(weewx_root)}, root)
    historybackfill.write_job(state_dir, {'config_path': str(conf), 'root': root, 'state_dir': state_dir,
                                          'default_binding': 'wx_binding', 'week_start': 6,
                                          'period_charts': dict(agg.SECTION, backfill_pause='0'), 'skin': {}})
    job_path = os.path.join(state_dir, 'job.json')
    held = hw.WorkerLock(state_dir).acquire()
    assert historybackfill.main(['--job', job_path]) == 0
    assert not os.path.exists(os.path.join(root, 'manifest.json'))
    held.release()
    assert historybackfill.main(['--job', job_path]) == 0
    index = hw.read_json(os.path.join(root, 'manifest.json'))
    assert index['backfill']['state'] == 'done'
    assert index['backfill']['total'] >= agg.DAYS
    day_id = hp.period_id('day', agg.FIRST_DAY + dt.timedelta(days=1))
    entry = hw.read_json(os.path.join(root, 'manifest', 'day', day_id[:4] + '.json'))['entries'][day_id]
    assert entry['s'] == 'ok'
    data = hw.read_json(os.path.join(root, *entry['file'].split('/')))
    assert data['state'] == 'complete'
    assert data['coverage']['records'] == 288
    assert not os.path.exists(os.path.join(state_dir, 'worker.lock'))
    assert hw.read_json(os.path.join(state_dir, 'worker.json'))['state'] == 'done'

def test_config_hash_survives_job_serialisation():
    configobj = pytest.importorskip('configobj')
    pytest.importorskip('weewx')
    from user.historybackfill import plain
    from user.historydata import config_hash
    skin = configobj.ConfigObj({'PeriodCharts': {'refresh': {'day': '0', 'week': '3600'},
                                                 'period_chart_items': ['outTemp', 'rain'],
                                                 'outTemp': {'outTemp': {'aggregate_type': 'avg'}},
                                                 'rain': {'rain': {'aggregate_type': 'sum'}}}})
    restored = json.loads(json.dumps(plain(skin['PeriodCharts'])))
    a = config_hash(PeriodChartsConfig(skin['PeriodCharts'], 'wx_binding'), 6, BERLIN)
    b = config_hash(PeriodChartsConfig(restored, 'wx_binding'), 6, BERLIN)
    assert a == b
