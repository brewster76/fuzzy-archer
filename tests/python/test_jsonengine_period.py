import types

import pytest


def make_generator(skin_dict):
    jsonengine = pytest.importorskip('user.jsonengine')
    gen = types.SimpleNamespace(
        skin_dict=skin_dict,
        config_dict={'Station': {'week_start': '0'}, 'StdArchive': {'archive_interval': '300'}},
        stn_info=None,
        units_dict={'Groups': {'group_temperature': 'degree_C'},
                    'TimeFormats': {'period_title_month': '%B %Y'}},
        labels_dict={'Generic': {'outTemp': 'Außentemperatur'}},
        frontend_data={'charts': {'live': 'unchanged'}})
    return jsonengine, gen


def test_add_period_data():
    pytest.importorskip('weewx')
    skin = {'PeriodCharts': {'period_chart_items': ['outTemp'], 'outTemp': {'outTemp': {}}}}
    jsonengine, gen = make_generator(skin)
    jsonengine.JSONGenerator.add_period_data(gen)
    data = gen.frontend_data
    assert data['charts'] == {'live': 'unchanged'}
    series = data['period_charts']['charts']['outTemp']['series']['outTemp']
    assert series['label'] == 'Außentemperatur'
    assert series['target_unit'] == 'degree_C'
    assert data['period_config']['week_start'] == 0
    assert data['period_titles']['month'] == '%B %Y'
    assert len(data['period_titles']['month_names']) == 12


def test_add_period_data_without_section_or_on_error():
    pytest.importorskip('weewx')
    jsonengine, gen = make_generator({})
    jsonengine.JSONGenerator.add_period_data(gen)
    assert set(gen.frontend_data) == {'charts'}
    jsonengine, gen = make_generator({'PeriodCharts': {'period_chart_items': ['outTemp'], 'outTemp': {'outTemp': {}}}})
    gen.config_dict['Station']['week_start'] = '9'  # invalid -> keys omitted, Live data untouched
    jsonengine.JSONGenerator.add_period_data(gen)
    assert set(gen.frontend_data) == {'charts'}


def test_live_history_of_unknown_obs_type_is_empty(tmp_path):
    weewx = pytest.importorskip('weewx')
    import weewx.manager
    import weewx.schemas.wview
    jsonengine = pytest.importorskip('user.jsonengine')
    manager = weewx.manager.DaySummaryManager.open_with_create(
        {'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'weewx.sdb')}, schema=weewx.schemas.wview.schema)
    try:
        manager.addRecord({'dateTime': 1767229200, 'usUnits': weewx.US, 'interval': 5, 'outTemp': 50.0})
        gen = types.SimpleNamespace(
            frontend_data={}, first_timestamp=1767225600, lastGoodStamp=1767229200,
            db_binder=types.SimpleNamespace(get_manager=lambda binding=None: manager),
            get_target_unit=lambda obs: '')
        result = jsonengine.JSONGenerator.gen_history_data(
            gen, 'lightning_strike_count', {'showMaxMarkPoint': 'true'}, None)
        assert result == (1, [], [])
    finally:
        manager.close()


def test_live_gauge_data_items_include_radar_observations_only_when_enabled():
    pytest.importorskip('weewx')
    jsonengine = pytest.importorskip('user.jsonengine')
    gauges = {'live_gauge_items': ['outTemp', 'windSpeed'], 'wind_radar': {'enabled': 'false'}}
    assert jsonengine.live_gauge_data_items(gauges) == ['outTemp', 'windSpeed']

    gauges['wind_radar']['enabled'] = 'true'
    assert jsonengine.live_gauge_data_items(gauges) == [
        'outTemp', 'windSpeed', 'windDir', 'windGust']


def test_utc_offset_string():
    jsonengine = pytest.importorskip('user.jsonengine')
    assert jsonengine.utc_offset_string(3600) == '+01:00'
    assert jsonengine.utc_offset_string(0) == '+00:00'
    assert jsonengine.utc_offset_string(19800) == '+05:30'
    assert jsonengine.utc_offset_string(-12600) == '-03:30'
    assert jsonengine.utc_offset_string(-18000.0) == '-05:00'


def test_empty_database_generates_nothing(tmp_path):
    weewx = pytest.importorskip('weewx')
    import weewx.manager
    import weewx.schemas.wview
    jsonengine = pytest.importorskip('user.jsonengine')
    manager = weewx.manager.DaySummaryManager.open_with_create(
        {'driver': 'weedb.sqlite', 'database_name': str(tmp_path / 'weewx.sdb')}, schema=weewx.schemas.wview.schema)
    try:
        gen = types.SimpleNamespace(
            skin_dict={'JSONGenerator': {'enabled': 'true'}, 'LiveGauges': {}, 'LiveCharts': {},
                       'Units': {'Groups': {}}, 'Labels': {}},
            config_dict={}, db_binder=types.SimpleNamespace(get_manager=lambda binding=None: manager))
        gen.setup = lambda: jsonengine.JSONGenerator.setup(gen)
        gen.gen_data = lambda: pytest.fail('gen_data must not run without archive records')
        jsonengine.JSONGenerator.run(gen)
        assert gen.lastGoodStamp is None
    finally:
        manager.close()
