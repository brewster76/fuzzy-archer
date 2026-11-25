"""historygenerator against a real WeeWX database without lightning columns (set WEEWX_SRC)."""
import os
import types

import pytest

configobj = pytest.importorskip('configobj')
weewx = pytest.importorskip('weewx')
pytest.importorskip('Cheetah')
import weewx.manager  # noqa: E402
import weewx.schemas.wview  # noqa: E402
import weewx.units  # noqa: E402

from user.historygenerator import MyXSearch  # noqa: E402

SKIN_CONF = os.path.join(os.path.dirname(__file__), '..', '..', 'skins', 'Bootstrap', 'skin.conf')
START = 1767225600  # 2026-01-01 00:00 UTC


@pytest.fixture(scope='module')
def db(tmp_path_factory):
    path = str(tmp_path_factory.mktemp('db') / 'weewx.sdb')
    # Legacy wview schema: no lightning_strike_count column
    manager = weewx.manager.DaySummaryManager.open_with_create(
        {'driver': 'weedb.sqlite', 'database_name': path}, schema=weewx.schemas.wview.schema)
    manager.addRecord({'dateTime': ts, 'usUnits': weewx.US, 'interval': 60, 'outTemp': 50.0 + (ts // 3600) % 24,
                       'rain': 0.01, 'windSpeed': 5.0, 'windGust': 8.0, 'windDir': 90.0}
                      for ts in range(START + 3600, START + 3 * 86400 + 1, 3600))
    yield manager
    manager.close()


def make_search(tmp_path, history_items=None):
    import weeutil.config
    import weewx.defaults
    skin_dict = weeutil.config.deep_copy(weewx.defaults.defaults)  # as weewx.reportengine does
    weeutil.config.merge_config(skin_dict, configobj.ConfigObj(SKIN_CONF, encoding='utf-8', interpolation=False))
    skin_dict['HTML_ROOT'] = str(tmp_path)
    if history_items is not None:
        skin_dict['HistoryReport']['history_items'] = history_items
    generator = types.SimpleNamespace(
        skin_dict=skin_dict, config_dict={'WEEWX_ROOT': str(tmp_path)},
        formatter=weewx.units.Formatter.fromSkinDict(skin_dict),
        converter=weewx.units.Converter.fromSkinDict(skin_dict))
    return MyXSearch(generator)


def tables(search, db):
    extension = search.get_extension_list(None, lambda data_binding=None: db)[0]
    return extension['history_tables']


def test_only_history_items_are_built(tmp_path, db):
    built = tables(make_search(tmp_path), db)
    assert set(built) == {'min_temp', 'avg_temp', 'max_temp', 'rain', 'rain_days', 'max_wind', 'NOAA'}
    assert built['min_temp']['year']


def test_table_with_unknown_obs_type_is_skipped(tmp_path, db, caplog):
    search = make_search(tmp_path, ['min_temp', 'lightning_strike_count'])
    built = tables(search, db)
    assert set(built) == {'min_temp'}
    assert "[HistoryReport][[lightning_strike_count]] skipped" in caplog.text
    caplog.clear()
    search.cache_time = 0
    tables(search, db)
    assert 'skipped' not in caplog.text  # warned once only


def test_count_fallback_is_a_value_tuple(tmp_path):
    search = make_search(tmp_path)
    value = search.getCount(object(), 'max_ge', 1.0, 'mm', 'rain')  # query fails -> fallback
    assert value == (0, 'count', 'group_count')
    entry = {'sum': None, 'count': 0, 'max': None}
    search.aggregate_period(value, entry, 'max_ge', True)
    assert entry['count'] == 1 and entry['max'].value == 0


def test_format_cell_uses_summary_colors_and_optional_font_colors():
    from user.historygenerator import FormatCell
    rain_mm = {'minvalues': ['0', '10'], 'colors': ['#m0', '#m1'],
               'summary': {'minvalues': ['0', '1000', '1400'], 'colors': ['#s0', '#s1', '#s2'],
                           'fontColors': ['#f0', '#f1', '#f2']}}
    settings = {'format_string': '%.1f', 'table_options': {'obs_type': 'rain'},
                'color_dict': {'rain': {'mm': rain_mm}}}
    cell = FormatCell(None)
    summary = cell.format_cell(weewx.units.ValueTuple(1500.0, 'mm', 'group_rain'), settings, summary=True)
    assert (summary['background_color'], summary['font_color']) == ('#s2', '#f2')
    month = cell.format_cell(weewx.units.ValueTuple(15.0, 'mm', 'group_rain'), settings)
    assert (month['background_color'], month['font_color']) == ('#m1', '#000000')
