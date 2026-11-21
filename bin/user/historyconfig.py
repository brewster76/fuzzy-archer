# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
"""Resolution of the [PeriodCharts] skin configuration into per-view series and observation plans.

Works on plain dicts (configobj sections are dicts). See docs/historic-data-contract.md, section 6.
"""

import logging
import math

from user.historyperiods import PERIODS, NATIVE, normalize_resolution

log = logging.getLogger(__name__)

PLOT_TYPES = ('line', 'bar', 'scatter')
SUPPORTED_AGGREGATES = ('avg', 'sum', 'min', 'max', 'count', 'first', 'last', 'vecdir', 'vecavg')
SUPPORTED_STATISTICS = ('min', 'max', 'avg', 'sum', 'vecavg', 'vecdir')
WIND_COMPONENTS = ('windDir', 'windSpeed')
VECTOR_AGGREGATES = ('vecdir', 'vecavg')

DEFAULT_REFRESH = {'day': 0, 'week': 3600, 'month': 10800, 'year': 21600}
DEFAULT_VIEW_RESOLUTIONS = {
    'day': {'line': NATIVE, 'bar': NATIVE},
    'week': {'line': 'PT15M', 'bar': 'PT1H'},
    'month': {'line': 'PT2H', 'bar': 'P1D'},
    'year': {'line': 'P1D', 'bar': 'P1D'},
}


class ConfigError(ValueError):
    pass


def as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(',') if v.strip()]


def as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ('true', 'yes', 'on', '1'):
        return True
    if text in ('false', 'no', 'off', '0', ''):
        return False
    raise ConfigError("Not a boolean: '%s'" % value)


def _number(value, default, cast):
    if value is None or str(value).strip() == '':
        return default
    return cast(value)


def default_statistics(aggregate_type, data_type):
    """Contract 6.2. Wind direction always uses vector statistics."""
    if aggregate_type == 'sum':
        return ['sum', 'max']
    if aggregate_type in VECTOR_AGGREGATES or data_type in ('windDir', 'wind'):
        return ['vecavg', 'vecdir']
    return ['min', 'max', 'avg']


def observation_key(binding, data_type):
    return '%s/%s' % (binding, data_type)


def series_key(binding, data_type, aggregate_type, resolution):
    return '%s/%s/%s/%s' % (binding, data_type, aggregate_type if resolution != NATIVE else 'none', resolution)


class ViewSeries(object):
    """A series as computed for one view (day/week/month/year)."""

    def __init__(self, binding, data_type, aggregate_type, resolution, statistics, show=True):
        self.binding = binding
        self.data_type = data_type
        self.aggregate_type = aggregate_type if resolution != NATIVE else None
        self.resolution = resolution
        self.statistics = statistics
        self.show = show
        self.key = series_key(binding, data_type, self.aggregate_type, resolution)
        self.obs_key = observation_key(binding, data_type)

    def to_dict(self):
        return {'key': self.key, 'observation': self.obs_key, 'data_binding': self.binding,
                'data_type': self.data_type, 'aggregate_type': self.aggregate_type or 'none',
                'resolution': self.resolution, 'statistics': list(self.statistics), 'show': self.show}


class SeriesConfig(object):
    def __init__(self, chart_id, series_id, options, views):
        self.chart_id = chart_id
        self.series_id = series_id
        self.options = options      # scalar display options
        self.views = views          # view -> ViewSeries


class ChartConfig(object):
    def __init__(self, chart_id, options, series):
        self.chart_id = chart_id
        self.options = options
        self.series = series


class PeriodChartsConfig(object):
    """Resolved [PeriodCharts] configuration."""

    def __init__(self, section, default_binding='wx_binding'):
        section = section or {}
        self.default_binding = default_binding
        self.errors = []
        self.chart_items = as_list(section.get('period_chart_items'))
        self.generate = as_bool(section.get('generate'), True)
        self.data_url = str(section.get('data_url') or 'historic_data').strip().strip('/') or 'historic_data'
        self.show_daynight = as_bool(section.get('show_daynight'), True)
        self.transition_angle = _number(section.get('transition_angle'), 8, int)
        self.state_root = (section.get('state_root') or '').strip() or None
        self.max_retries = _number(section.get('max_retries'), 3, int)
        self.retry_backoff = _number(section.get('retry_backoff'), 600, int)
        self.backfill_pause = _number(section.get('backfill_pause'), 0.02, float)
        try:
            self.gap_threshold = _number(section.get('gap_threshold'), 1.0, float)
        except ValueError as e:
            raise ConfigError("gap_threshold must be a percentage between 0 and 100") from e
        if not math.isfinite(self.gap_threshold) or not 0 <= self.gap_threshold <= 100:
            raise ConfigError("gap_threshold must be a percentage between 0 and 100")

        refresh = section.get('refresh') or {}
        self.refresh = dict((view, _number(refresh.get(view), DEFAULT_REFRESH[view], int)) for view in PERIODS)

        defaults = section.get('defaults') or {}
        self.line_aggregate_type = str(defaults.get('line_aggregate_type') or 'avg').strip()
        self.view_resolutions = {}
        for view in PERIODS:
            view_defaults = defaults.get(view) or {}
            self.view_resolutions[view] = {}
            for kind in ('line', 'bar'):
                value = view_defaults.get(kind, DEFAULT_VIEW_RESOLUTIONS[view][kind])
                self.view_resolutions[view][kind] = normalize_resolution(value)

        self.charts = []
        for chart_id in self.chart_items:
            chart_section = section.get(chart_id)
            if not isinstance(chart_section, dict):
                self._error("[PeriodCharts] chart '%s' listed in period_chart_items has no section" % chart_id)
                continue
            chart = self._resolve_chart(chart_id, chart_section)
            if chart.series:
                self.charts.append(chart)

    def _error(self, message):
        log.error(message)
        self.errors.append(message)

    def _resolve_chart(self, chart_id, chart_section):
        options = dict((k, v) for k, v in chart_section.items() if not isinstance(v, dict))
        series = []
        for series_id, series_section in chart_section.items():
            if not isinstance(series_section, dict):
                continue
            try:
                series.append(self._resolve_series(chart_id, series_id, series_section))
            except (ConfigError, ValueError) as e:
                self._error("[PeriodCharts] [[%s]] [[[%s]]]: %s. Series skipped." % (chart_id, series_id, e))
        return ChartConfig(chart_id, options, series)

    def _resolve_series(self, chart_id, series_id, section):
        options = dict((k, v) for k, v in section.items() if not isinstance(v, dict))
        binding = str(section.get('data_binding') or self.default_binding).strip()
        data_type = str(section.get('obs_type') or section.get('data_type') or series_id).strip()
        plot_type = str(section.get('plotType') or 'line').strip()
        if plot_type not in PLOT_TYPES:
            raise ConfigError("unknown plotType '%s'" % plot_type)
        if '/' in binding or '/' in data_type:
            raise ConfigError("data_binding and data_type must not contain '/'")
        explicit_statistics = as_list(section.get('statistics')) if 'statistics' in section else None
        if explicit_statistics is not None:
            unknown = [s for s in explicit_statistics if s not in SUPPORTED_STATISTICS]
            if unknown:
                raise ConfigError("unsupported statistics %s" % unknown)

        views = {}
        for view in PERIODS:
            view_section = section.get(view) if isinstance(section.get(view), dict) else {}
            views[view] = self._resolve_view(view, data_type, binding, plot_type, section,
                                             view_section, explicit_statistics)
        return SeriesConfig(chart_id, series_id, options, views)

    def _resolve_view(self, view, data_type, binding, plot_type, section, view_section, explicit_statistics):
        # 6.1 priority: per-view > series > view default (> native fallback for day, part of defaults)
        resolution = view_section.get('aggregateInterval', section.get('aggregateInterval'))
        resolution = normalize_resolution(resolution) if resolution is not None else \
            self.view_resolutions[view]['bar' if plot_type == 'bar' else 'line']
        aggregate_type = view_section.get('aggregateType', section.get('aggregateType'))
        aggregate_type = str(aggregate_type).strip() if aggregate_type is not None else None

        effective_type = data_type
        if resolution != NATIVE:
            if aggregate_type is None:
                if plot_type == 'bar':
                    raise ConfigError("bar series with resolution %s in view '%s' needs aggregateType"
                                      % (resolution, view))
                aggregate_type = 'vecdir' if data_type == 'windDir' else self.line_aggregate_type
            if aggregate_type not in SUPPORTED_AGGREGATES:
                raise ConfigError("unsupported aggregateType '%s'" % aggregate_type)
            if aggregate_type in VECTOR_AGGREGATES:
                if data_type not in WIND_COMPONENTS + ('wind',):
                    raise ConfigError("%s is only supported for wind" % aggregate_type)
                effective_type = 'wind'
        else:
            aggregate_type = None

        statistics = explicit_statistics if explicit_statistics is not None \
            else default_statistics(aggregate_type, effective_type)
        show = as_bool(view_section.get('show'), True)
        return ViewSeries(binding, effective_type, aggregate_type, resolution, statistics, show)

    # -----------------------------------------------------------------------------------------

    def view_plan(self, view):
        """(series, observations) for one view.

        series: ordered dict series_key -> ViewSeries (deduplicated)
        observations: dict obs_key -> {'data_binding', 'data_type', 'statistics': [..]} (union of stats)
        """
        series = {}
        observations = {}
        for chart in self.charts:
            for s in chart.series:
                vs = s.views[view]
                if not vs.show:
                    continue
                series.setdefault(vs.key, vs)
                obs = observations.setdefault(vs.obs_key, {'data_binding': vs.binding,
                                                           'data_type': vs.data_type,
                                                           'statistics': []})
                for stat in vs.statistics:
                    if stat not in obs['statistics']:
                        obs['statistics'].append(stat)
        return series, observations

    def to_frontend(self):
        """Chart definitions for weewxData.json 'period_charts' (labels / units are added by the caller)."""
        result = {}
        for chart in self.charts:
            chart_dict = dict(chart.options)
            chart_dict['series'] = {}
            for s in chart.series:
                series_dict = dict(s.options)
                series_dict['views'] = dict((view, vs.to_dict()) for view, vs in s.views.items())
                chart_dict['series'][s.series_id] = series_dict
            result[chart.chart_id] = chart_dict
        return {'order': [c.chart_id for c in self.charts], 'charts': result}

    def signature(self):
        """Stable description of everything that influences generated files (for regeneration detection)."""
        views = {}
        for view in PERIODS:
            series, observations = self.view_plan(view)
            views[view] = {'series': sorted(series), 'observations':
                           dict((k, sorted(v['statistics'])) for k, v in sorted(observations.items()))}
        return {'views': views, 'show_daynight': self.show_daynight,
                'transition_angle': self.transition_angle, 'gap_threshold': self.gap_threshold}


# ---------------------------------------------------------------------------------------------
# weewxData.json additions (contract 8), used by user.jsonengine
# ---------------------------------------------------------------------------------------------

DEFAULT_TITLE_FORMATS = {'day': '%x', 'week': '%x', 'month': '%B %Y', 'year': '%Y'}
# Tokens the frontend formatter understands; everything else is passed through literally.
TITLE_TOKENS = ('%d', '%e', '%m', '%y', '%Y', '%b', '%B', '%a', '%A', '%%')
_REFERENCE_DATE = (2033, 11, 22)   # all fields distinguishable: 2033 / 33 / 11 / 22


def locale_date_pattern(strftime=None):
    """Pattern of the locale's %x using only %d/%m/%y/%Y, derived from a reference date
    (nl_langinfo is not available on every platform)."""
    import datetime
    fmt_date = strftime or (lambda fmt: datetime.date(*_REFERENCE_DATE).strftime(fmt))
    text = fmt_date('%x')
    names = [(fmt_date('%' + t), t) for t in ('B', 'A', 'b', 'a')]
    for value, token in sorted(names, key=lambda n: -len(n[0])) + [('2033', 'Y'), ('33', 'y'), ('11', 'm'),
                                                                  ('22', 'd')]:
        if value:
            text = text.replace(value, '\0' + token)
    return text.replace('%', '%%').replace('\0', '%')


def resolve_title_format(fmt, date_pattern):
    """Replace %x (and %D) by the locale date pattern; other tokens stay for the frontend."""
    result = []
    i = 0
    while i < len(fmt):
        if fmt[i] == '%' and i + 1 < len(fmt):
            token = fmt[i:i + 2]
            result.append(date_pattern if token in ('%x', '%D') else token)
            i += 2
        else:
            result.append(fmt[i])
            i += 1
    return ''.join(result)


def period_titles(time_formats, strftime=None):
    """'period_titles' for weewxData.json: formats per view plus localized month/day names.

    `time_formats` is the [Units][[TimeFormats]] section; strftime(fmt, date) defaults to the active locale.
    """
    import datetime
    if strftime is None:
        def strftime(fmt, date):
            return date.strftime(fmt)
    time_formats = time_formats or {}
    pattern = locale_date_pattern(lambda fmt: strftime(fmt, datetime.date(*_REFERENCE_DATE)))
    titles = {}
    for view in PERIODS:
        fmt = time_formats.get('period_title_' + view) or DEFAULT_TITLE_FORMATS[view]
        if isinstance(fmt, (list, tuple)):
            fmt = ', '.join(fmt)  # configobj splits unquoted values containing commas
        titles[view] = resolve_title_format(str(fmt), pattern)
    months = [datetime.date(2001, m, 1) for m in range(1, 13)]
    days = [datetime.date(2001, 1, 1) + datetime.timedelta(days=d) for d in range(7)]  # 2001-01-01 = Monday
    titles['month_names'] = [strftime('%B', d) for d in months]
    titles['month_abbr'] = [strftime('%b', d) for d in months]
    titles['day_names'] = [strftime('%A', d) for d in days]   # Monday first (WeeWX week_start encoding)
    titles['day_abbr'] = [strftime('%a', d) for d in days]
    return titles


def frontend_charts(config, obs_group_of, target_unit_of, generic_labels=None):
    """'period_charts' for weewxData.json: to_frontend() plus label, obs_group and target_unit per
    series and view (vecdir is always group_direction)."""
    generic_labels = generic_labels or {}
    result = config.to_frontend()
    for chart in config.charts:
        chart_dict = result['charts'][chart.chart_id]
        for s in chart.series:
            series_dict = chart_dict['series'][s.series_id]
            data_type = str(s.options.get('obs_type') or s.options.get('data_type') or s.series_id)
            series_dict['data_type'] = data_type
            series_dict['label'] = str(s.options.get('seriesName') or generic_labels.get(data_type) or data_type)
            series_dict['obs_group'] = obs_group_of(data_type)
            series_dict['target_unit'] = target_unit_of(series_dict['obs_group'])
            for view, vs in s.views.items():
                group = 'group_direction' if vs.aggregate_type == 'vecdir' else series_dict['obs_group']
                series_dict['views'][view]['obs_group'] = group
                series_dict['views'][view]['target_unit'] = target_unit_of(group)
    return result


def frontend_config(config, week_start, archive_interval):
    """'period_config' for weewxData.json."""
    return {'data_url': config.data_url, 'generate': config.generate, 'week_start': int(week_start),
            'refresh': dict(config.refresh), 'archive_interval': int(archive_interval),
            'gap_threshold': config.gap_threshold,
            'show_daynight': config.show_daynight, 'view_resolutions': config.view_resolutions,
            'errors': list(config.errors)}
