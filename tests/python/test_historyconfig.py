from user.historyconfig import PeriodChartsConfig, default_statistics

SECTION = {
    'period_chart_items': ['outTemp', 'rain', 'windDir', 'missing', 'broken'],
    'refresh': {'week': '600'},
    'defaults': {'week': {'line': '1800'}},
    'outTemp': {
        'animation': 'false',
        'outTemp': {'lineColor': '#b44242', 'day': {'aggregateInterval': 'PT5M'}},
        'dewpoint': {'statistics': 'min, max'},
    },
    'rain': {'rain': {'plotType': 'bar', 'aggregateType': 'sum', 'aggregateInterval': '1800',
                      'year': {'aggregateInterval': 'P1D'}}},
    'windDir': {'windDir': {'symbol': 'circle'}},
    'broken': {'UV': {'plotType': 'bar'}},
}


def config():
    return PeriodChartsConfig(SECTION, 'wx_binding')


def test_options_and_defaults():
    c = config()
    assert c.generate and c.data_url == 'historic_data'
    assert c.refresh == {'day': 0, 'week': 600, 'month': 10800, 'year': 21600}
    assert c.view_resolutions['week'] == {'line': 'PT30M', 'bar': 'PT1H'}
    assert [ch.chart_id for ch in c.charts] == ['outTemp', 'rain', 'windDir']
    assert len(c.errors) == 2  # missing section, bar without aggregateType
    assert any('UV' in e for e in c.errors)


def test_priority_and_keys():
    c = config()
    temp = c.charts[0].series[0].views
    assert temp['day'].key == 'wx_binding/outTemp/avg/PT5M'
    assert temp['week'].key == 'wx_binding/outTemp/avg/PT30M'
    assert temp['year'].key == 'wx_binding/outTemp/avg/P1D'
    rain = c.charts[1].series[0].views
    assert rain['day'].key == 'wx_binding/rain/sum/PT30M'
    assert rain['year'].key == 'wx_binding/rain/sum/P1D'
    assert rain['week'].statistics == ['sum', 'max']
    wind = c.charts[2].series[0].views
    assert wind['day'].key == 'wx_binding/windDir/none/native'
    assert wind['day'].statistics == ['vecavg', 'vecdir']
    assert wind['week'].key == 'wx_binding/wind/vecdir/PT30M'
    assert wind['week'].obs_key == 'wx_binding/wind'


def test_view_plan_union_and_dedupe():
    section = dict(SECTION)
    section['period_chart_items'] = ['outTemp', 'copy']
    section['copy'] = {'outTemp': {'statistics': 'sum'}}
    c = PeriodChartsConfig(section, 'wx_binding')
    series, observations = c.view_plan('month')
    assert list(series) == ['wx_binding/outTemp/avg/PT2H', 'wx_binding/dewpoint/avg/PT2H']
    assert observations['wx_binding/outTemp']['statistics'] == ['min', 'max', 'avg', 'sum']
    assert observations['wx_binding/dewpoint']['statistics'] == ['min', 'max']


def test_frontend_export():
    exported = config().to_frontend()
    assert exported['order'] == ['outTemp', 'rain', 'windDir']
    series = exported['charts']['outTemp']['series']['outTemp']
    assert series['lineColor'] == '#b44242'
    assert series['views']['week']['resolution'] == 'PT30M'
    assert exported['charts']['outTemp']['animation'] == 'false'


def test_default_statistics():
    assert default_statistics('sum', 'rain') == ['sum', 'max']
    assert default_statistics('vecdir', 'wind') == ['vecavg', 'vecdir']
    assert default_statistics(None, 'outTemp') == ['min', 'max', 'avg']


# --- weewxData.json additions -----------------------------------------------------------------

import datetime as _dt

from user.historyconfig import (frontend_charts, frontend_config, locale_date_pattern, period_titles,
                                resolve_title_format)

GERMAN = {'%x': '22.11.2033', '%B': 'November', '%b': 'Nov', '%A': 'Dienstag', '%a': 'Di'}


def german_strftime(fmt, date=None):
    if date is not None and date != _dt.date(2033, 11, 22):
        months = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September',
                  'Oktober', 'November', 'Dezember']
        days = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
        return {'%B': months[date.month - 1], '%b': months[date.month - 1][:3],
                '%A': days[date.weekday()], '%a': days[date.weekday()][:2]}[fmt]
    return GERMAN[fmt]


def test_locale_date_pattern():
    assert locale_date_pattern(lambda f: {'%x': '22.11.2033'}.get(f, '')) == '%d.%m.%Y'
    assert locale_date_pattern(lambda f: {'%x': '11/22/33'}.get(f, '')) == '%m/%d/%y'
    assert locale_date_pattern(lambda f: {'%x': '2033-11-22'}.get(f, '')) == '%Y-%m-%d'
    assert locale_date_pattern(lambda f: {'%x': '22 November 2033 (100%)', '%B': 'November'}.get(f, '')) \
        == '%d %B %Y (100%%)'
    assert '%' in locale_date_pattern()  # active locale of the test process


def test_resolve_title_format():
    assert resolve_title_format('%x', '%d.%m.%Y') == '%d.%m.%Y'
    assert resolve_title_format('KW ab %x %% %B', '%d.%m.%Y') == 'KW ab %d.%m.%Y %% %B'
    assert resolve_title_format('100%', 'p') == '100%'


def test_period_titles():
    titles = period_titles({'period_title_month': '%B %Y', 'period_title_week': ['%a', ' %x']}, german_strftime)
    assert titles['day'] == '%d.%m.%Y' and titles['year'] == '%Y' and titles['month'] == '%B %Y'
    assert titles['week'] == '%a,  %d.%m.%Y'
    assert titles['month_names'][2] == 'März' and len(titles['month_abbr']) == 12
    assert titles['day_names'][0] == 'Montag' and titles['day_abbr'][6] == 'So'
    assert period_titles(None, german_strftime)['week'] == '%d.%m.%Y'


def test_frontend_charts_and_config():
    section = {'period_chart_items': ['wind', 'rain'],
               'wind': {'windDir': {'plotType': 'scatter'}, 'windSpeed': {'seriesName': 'Mean'}},
               'rain': {'rain': {'plotType': 'bar', 'aggregateType': 'sum'}}}
    config = PeriodChartsConfig(section, 'wx_binding')
    groups = {'windDir': 'group_direction', 'windSpeed': 'group_speed', 'rain': 'group_rain'}
    units = {'group_direction': 'degree_compass', 'group_speed': 'km_per_hour', 'group_rain': 'mm'}
    charts = frontend_charts(config, groups.get, units.get, {'windDir': 'Windrichtung', 'rain': 'Regen'})
    assert charts['order'] == ['wind', 'rain']
    wind_dir = charts['charts']['wind']['series']['windDir']
    assert wind_dir['label'] == 'Windrichtung' and wind_dir['target_unit'] == 'degree_compass'
    assert wind_dir['views']['week']['key'] == 'wx_binding/wind/vecdir/PT15M'
    assert wind_dir['views']['week']['obs_group'] == 'group_direction'
    speed = charts['charts']['wind']['series']['windSpeed']
    assert speed['label'] == 'Mean' and speed['views']['day']['target_unit'] == 'km_per_hour'
    assert charts['charts']['rain']['series']['rain']['views']['month']['key'] == 'wx_binding/rain/sum/P1D'
    cfg = frontend_config(config, 6, '300')
    assert cfg['week_start'] == 6 and cfg['archive_interval'] == 300 and cfg['data_url'] == 'historic_data'
    assert cfg['refresh']['week'] == 3600 and cfg['view_resolutions']['day']['line'] == 'native'
    import json
    json.dumps(charts), json.dumps(cfg)
