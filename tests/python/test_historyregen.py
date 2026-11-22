import datetime as dt
import os

import pytest

from user import historyperiods as hp
from user import historywriter as hw
from user.historyregen import parse_date, regenerate, series_matches

from test_historybackfill import FakeBuild, FakeDB, make, ts


class SeriesBuild(FakeBuild):
    def __call__(self, db_managers, binding, series, observations, zone, kind, period, period_id, span, now, **kw):
        data = FakeBuild.__call__(self, db_managers, binding, series, observations, zone, kind, period, period_id,
                                  span, now, **kw)
        data['series'] = dict((key, {'data': []}) for key in series
                              if not (getattr(self, 'drop', None) and self.drop in key))
        return data


SECTION2 = {'period_chart_items': ['outTemp', 'rain'], 'outTemp': {'outTemp': {}},
            'rain': {'rain': {'aggregate_type': 'sum'}}, 'backfill_pause': '0'}


def test_parse_date_and_series_match():
    assert parse_date('2024') == dt.date(2024, 1, 1)
    assert parse_date('2024', end=True) == dt.date(2024, 12, 31)
    assert parse_date('2024-02', end=True) == dt.date(2024, 2, 29)
    assert parse_date('2024-02-03') == dt.date(2024, 2, 3)
    for bad in ('2024-13', 'x', '2024-02-30', '2024-1-2-3'):
        with pytest.raises(ValueError):
            parse_date(bad)
    key = 'wx_binding/rain/sum/P1D'
    assert all(series_matches(key, s) for s in ('rain', 'wx_binding/rain', key))
    assert not series_matches(key, 'outTemp')


def test_regenerate_range_resets_errors_and_state(tmp_path):
    first, now = ts(2026, 11, 1), ts(2026, 11, 21, 18)
    db = FakeDB(first, now)
    make(tmp_path, db, now, FakeBuild(lambda p, pid: pid == '20261105')).run()
    worker = make(tmp_path, db, now, FakeBuild())
    m = hw.Manifest(worker.root, 6)
    m.set('day', '20261105', {'s': 'error', 'tries': 3})
    m.flush(now)
    hw.write_json(os.path.join(worker.state_directory, 'worker.json'), {'config': 'x', 'state': 'done'})
    build = FakeBuild()
    worker = make(tmp_path, db, now + 60, build)
    result = regenerate(worker, ['day'], dt.date(2026, 11, 4), dt.date(2026, 11, 6))
    assert build.calls == [('day', '20261106'), ('day', '20261105'), ('day', '20261104')]
    assert hw.Manifest(worker.root, 6).get('day', '20261105')['s'] == 'ok'
    assert len(result['regenerated']) == 3
    assert not result['failed']
    assert not os.path.exists(os.path.join(worker.state_directory, 'worker.json'))
    # month overlapping the range is still running; the running week (Sunday start) is excluded
    build = FakeBuild()
    regenerate(make(tmp_path, db, now + 60, build), ['month', 'week'], dt.date(2026, 11, 4), None)
    assert build.calls == [('week', '20261108'), ('week', '20261101')]


def test_regenerate_dry_run_writes_nothing(tmp_path):
    first, now = ts(2026, 11, 1), ts(2026, 11, 21, 18)
    db = FakeDB(first, now)
    build = FakeBuild()
    worker = make(tmp_path, db, now, build)
    result = regenerate(worker, list(hp.PERIODS), dry_run=True)
    assert build.calls == []
    assert ('day', '20261120') in result['planned']
    assert not os.path.exists(os.path.join(worker.root, 'manifest.json'))


def test_regenerate_weeks_after_week_start_change(tmp_path):
    first, now = ts(2026, 11, 1), ts(2026, 11, 21, 18)
    db = FakeDB(first, now)
    make(tmp_path, db, now, week_start=6).run()
    old_file = os.path.join(tmp_path, 'historic_data', 'week', '20261108.json.gz')
    assert os.path.exists(old_file)
    make(tmp_path, db, now + 60, week_start=0).run()  # marks incompatible, weeks blocked
    build = FakeBuild()
    worker = make(tmp_path, db, now + 120, build, week_start=0)
    result = regenerate(worker, ['week'])
    assert '20261108' in result['removed_weeks']
    assert not os.path.exists(old_file)
    assert build.calls == [('week', '20261109'), ('week', '20261102'), ('week', '20261026')]
    weeks = hw.Manifest(worker.root, 0).entries('week')
    assert set(weeks) == {'20261026', '20261102', '20261109'}
    assert all(e['s'] == 'ok' for e in weeks.values())
    # backfill no longer blocked: nothing left to do for weeks
    build = FakeBuild()
    make(tmp_path, db, now + 180, build, week_start=0).run()
    assert not any(p == 'week' for p, _ in build.calls)


def test_regenerate_missing_series_only(tmp_path):
    first, now = ts(2026, 11, 15), ts(2026, 11, 21, 18)
    db = FakeDB(first, now)
    build = SeriesBuild()
    build.drop = '/rain/'
    make(tmp_path, db, now, build, section=SECTION2).run()
    build = SeriesBuild()
    worker = make(tmp_path, db, now + 60, build, section=SECTION2)
    result = regenerate(worker, ['day'], series=['rain'])
    assert len(result['regenerated']) == 6
    build = SeriesBuild()
    result = regenerate(make(tmp_path, db, now + 120, build, section=SECTION2), ['day'], series=['rain', 'outTemp'])
    assert build.calls == []
    assert result['planned'] == []


SKIN_CONF = """
[PeriodCharts]
    backfill_pause = 0
    period_chart_items = outTemp,
    [[outTemp]]
        [[[outTemp]]]
[Generators]
    generator_list = user.historydata.PeriodDataGenerator,
"""


def test_main_end_to_end(tmp_path, monkeypatch, capsys):
    pytest.importorskip('configobj')
    pytest.importorskip('weewx')
    import configobj
    import weeutil.logger
    import weewx.manager
    import test_historyaggregate as agg
    from test_historybackfill import WEEWX_CONF
    from user import historyregen
    if not hasattr(__import__('socket'), 'AF_UNIX'):
        monkeypatch.setattr(weeutil.logger, 'setup', lambda *args, **kw: None)
    weewx_root = tmp_path / 'weewx'
    (weewx_root / 'archive').mkdir(parents=True)
    (weewx_root / 'skins' / 'Bootstrap').mkdir(parents=True)
    (weewx_root / 'skins' / 'Bootstrap' / 'skin.conf').write_text(SKIN_CONF)
    conf = weewx_root / 'weewx.conf'
    conf.write_text(WEEWX_CONF.format(root=str(weewx_root).replace('\\', '/')) +
                    "[StdReport]\n    SKIN_ROOT = skins\n    HTML_ROOT = public_html\n"
                    "    [[SeasonsReport]]\n        skin = Seasons\n        enable = false\n"
                    "    [[Bootstrap]]\n        skin = Bootstrap\n")
    binder = weewx.manager.DBBinder(configobj.ConfigObj(str(conf)))
    binder.get_manager('wx_binding', initialize=True).addRecord(agg.make_records())
    binder.close()
    root = str(weewx_root / 'public_html' / 'historic_data')
    day_id = hp.period_id('day', agg.FIRST_DAY + dt.timedelta(days=1))
    args = ['--config', str(conf), '--period', 'day']
    assert historyregen.main(args + ['--dry-run']) == 0
    assert 'would regenerate day %s' % day_id in capsys.readouterr().out
    held = hw.WorkerLock(hw.state_dir({'WEEWX_ROOT': str(weewx_root),
                                       'DatabaseTypes': {'SQLite': {'SQLITE_ROOT': 'archive'}}}, root)).acquire()
    assert historyregen.main(args) == 2
    held.release()
    assert historyregen.main(args + ['--from', day_id[:4] + '-' + day_id[4:6] + '-' + day_id[6:]]) == 0
    entry = hw.read_json(os.path.join(root, 'manifest', 'day', day_id[:4] + '.json'))['entries'][day_id]
    assert entry['s'] == 'ok'
    assert historyregen.main(args + ['--from', '2024-13']) == 3
    assert historyregen.main(args + ['--report', 'Nope']) == 3
