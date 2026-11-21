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
    assert series['label'] == 'Außentemperatur' and series['target_unit'] == 'degree_C'
    assert data['period_config']['week_start'] == 0
    assert data['period_titles']['month'] == '%B %Y' and len(data['period_titles']['month_names']) == 12


def test_add_period_data_without_section_or_on_error():
    pytest.importorskip('weewx')
    jsonengine, gen = make_generator({})
    jsonengine.JSONGenerator.add_period_data(gen)
    assert set(gen.frontend_data) == {'charts'}
    jsonengine, gen = make_generator({'PeriodCharts': {'period_chart_items': ['outTemp'], 'outTemp': {'outTemp': {}}}})
    gen.config_dict['Station']['week_start'] = '9'  # invalid -> keys omitted, Live data untouched
    jsonengine.JSONGenerator.add_period_data(gen)
    assert set(gen.frontend_data) == {'charts'}
