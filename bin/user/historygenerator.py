#
# Copyright (c) 2013-2016  Nick Dajda <nick.dajda@gmail.com>
#
# Distributed under the terms of the GNU GENERAL PUBLIC LICENSE
#
"""Extends the Cheetah generator search list to add html historic data tables in a nice color scheme.

Works with all databases.
Observes the units of measure and display formats specified in skin.conf.

WILL NOT WORK with Weewx prior to release 3.0.
  -- Use this version for 2.4 - 2.7:  https://github.com/brewster76/fuzzy-archer/releases/tag/v2.0

To use it, add this generator to search_list_extensions in skin.conf:

[CheetahGenerator]
    search_list_extensions = user.historygenerator.MyXSearch

1) The $alltime tag:

Allows tags such as $alltime.outTemp.max for the all-time max
temperature, or $seven_day.rain.sum for the total rainfall in the last
seven days.

2) Nice colorful tables summarising history data by month and year

Check out the preconfigured skin.conf [HistoryReport] Section
"""

from datetime import datetime
import time
import logging
import os.path

import weewx.units
import weeutil.weeutil
import math

try:
    from weeutil.weeutil import accumulateLeaves
except ImportError:
    from weeutil.config import accumulateLeaves
from weewx.cheetahgenerator import SearchList
from weewx.tags import TimespanBinder

log = logging.getLogger(__name__)

TABLE_GENERATION_ERROR = "Could not generate table [HistoryReport][[%s]]"


class MyXSearch(SearchList):
    def __init__(self, generator):
        SearchList.__init__(self, generator)

        self.table_dict = generator.skin_dict['HistoryReport']
        self.color_dict = generator.skin_dict['HistoryColors']

        self.units_dict = generator.skin_dict['Units']

        # Calculate the tables once every refresh_interval mins
        self.refresh_interval = int(self.table_dict.get('refresh_interval', 5))
        self.cache_time = 0

        self.search_list_extension = {}
        self.search_list_extension['fuzzy_archer_version'] = generator.skin_dict['version'] if 'version' in generator.skin_dict else ''
        self.search_list_extension['css_mtime'] = self.last_mtime_resources('css', generator.config_dict['WEEWX_ROOT'], generator.skin_dict['HTML_ROOT'])
        self.search_list_extension['js_mtime'] = self.last_mtime_resources('js', generator.config_dict['WEEWX_ROOT'], generator.skin_dict['HTML_ROOT'])

        # Make some config available to templates
        self.add_to_extension_list('Navigation', generator.skin_dict)
        self.add_to_extension_list('StationInfo', generator.skin_dict)
        self.add_to_extension_list('TranslationLinks', generator.skin_dict)
        self.add_to_extension_list('HistoryReport', generator.skin_dict)
        self.add_to_extension_list('BootstrapLabels', generator.skin_dict)
        self.add_to_extension_list('Labels', generator.skin_dict)
        self.add_to_extension_list('Units', generator.skin_dict)
        self.add_to_extension_list('JSONGenerator', generator.skin_dict)
        self.add_to_extension_list('LiveGauges', generator.skin_dict)
        self.add_to_extension_list('Stats', generator.skin_dict)
        self.add_to_extension_list('News', generator.skin_dict)
        self.add_to_extension_list('LiveCharts', generator.skin_dict)
        self.add_to_extension_list('locale', generator.skin_dict)

    def add_to_extension_list(self, key, source):
        if key in source:
            self.search_list_extension[key] = source[key]
        else:
            log.debug("%s: No %s specific labels found" % (key, os.path.basename(__file__)))

    def get_extension_list(self, valid_timespan, db_lookup):
        """For weewx V3.x extensions. Should return a list
        of objects whose attributes or keys define the extension.

        valid_timespan:  An instance of weeutil.weeutil.TimeSpan. This will hold the
        start and stop times of the domain of valid times.

        db_lookup: A function with call signature db_lookup(data_binding), which
        returns a database manager and where data_binding is an optional binding
        name. If not given, then a default binding will be used.
        """

        if (time.time() - (self.refresh_interval * 60)) > self.cache_time:
            self.cache_time = time.time()
            self._refresh_history_tables(db_lookup)
        return [self.search_list_extension]

    def _refresh_history_tables(self, db_lookup):
        started = time.time()
        self.search_list_extension["history_tables"] = {}
        for table_key in self.table_dict.sections:
            self._build_history_table(table_key, db_lookup)
        log.debug("%s: Generated %d tables in %.2f seconds" %
                  (os.path.basename(__file__), len(self.search_list_extension["history_tables"]),
                   time.time() - started))

    def _build_history_table(self, table_key, db_lookup):
        table_options = accumulateLeaves(self.table_dict[table_key])
        binding = table_options.get('data_binding', 'wx_binding')
        manager = db_lookup(data_binding=binding)
        self.alltime_timespan = weeutil.weeutil.TimeSpan(manager.first_timestamp, manager.last_timestamp)
        all_stats = TimespanBinder(self.alltime_timespan, db_lookup, data_binding=binding,
                                   formatter=self.generator.formatter, converter=self.generator.converter)
        self.search_list_extension['alltime'] = all_stats
        table_stats = self._table_stats(table_options, binding, all_stats, db_lookup)
        new_table = {"year": [], "settings": {"table_options": table_options, "color_dict": self.color_dict}}
        self._statsDict(table_key, new_table, table_options, table_stats, binding)
        self.search_list_extension["history_tables"][table_key] = new_table

    def _table_stats(self, table_options, binding, all_stats, db_lookup):
        startdate = table_options.get('startdate')
        if startdate is None:
            return all_stats
        startdate = weeutil.weeutil.startOfDay(int(startdate))
        end = db_lookup(binding).last_timestamp
        table_timespan = weeutil.weeutil.TimeSpan(int(startdate), end)
        return TimespanBinder(table_timespan, db_lookup, data_binding=binding,
                              formatter=self.generator.formatter, converter=self.generator.converter)

    def _parseTableOptions(self, table_options, table_key):
        if table_key == 'NOAA':
            return 'NOAA', None

        obs_type = table_options.get('obs_type')
        colors_key = obs_type
        unit = self.units_dict["Groups"][weewx.units.obs_group_dict[obs_type]]
        if "colors" in table_options:
            colors_key = table_options.get("colors")[0]
            unit = table_options.get("colors")[1]

        table_colors = self._table_colors(colors_key, unit, table_key)
        if table_colors is None:
            return None, None
        if not self._valid_color_lengths(table_colors, table_key):
            return None, None
        summary_colors = self._summary_colors(colors_key, unit)
        if summary_colors is not None and not self._valid_color_lengths(summary_colors, table_key, summary=True):
            return None, None
        summary_cell_colors = self._cell_colors(summary_colors) if summary_colors is not None else None
        return self._cell_colors(table_colors), summary_cell_colors

    def _table_colors(self, colors_key, unit, table_key):
        if colors_key in self.color_dict and unit in self.color_dict[colors_key]:
            return self.color_dict[colors_key][unit]
        log.info("No colors defined for [HistoryReport][[%s]]" % table_key)
        return {"minvalues": [0], "colors": ["#ffffff"]}

    def _summary_colors(self, colors_key, unit):
        if colors_key in self.color_dict and unit in self.color_dict[colors_key]:
            return self.color_dict[colors_key][unit].get('summary')
        return None

    @staticmethod
    def _valid_color_lengths(colors, table_key, summary=False):
        length = len(colors['minvalues'])
        if len(colors['colors']) == length:
            return True
        suffix = '[summary]' if summary else ''
        log.info("%s: minvalues and colors must have the same number of elements in "
                 "[HistoryReport][[%s]]%s" % (os.path.basename(__file__), table_key, suffix))
        return False

    @staticmethod
    def _cell_colors(colors):
        length = len(colors['minvalues'])
        font_colors = colors.get('fontColors', ['#000000'] * length)
        return list(zip(colors['minvalues'], colors['colors'], font_colors))

    def _statsDict(self, table_key, data_table, table_options, table_stats, binding):
        """
        table_options: Dictionary containing skin.conf options for particluar table
        all_stats: Link to all_stats TimespanBinder
        """
        
        if table_key == 'NOAA':
            return self._statsDictNOAA(data_table, table_options, table_stats)

        cell_colors, summary_cell_colors = self._parseTableOptions(table_options, table_key)
        self._set_table_settings(data_table, table_options, table_key, cell_colors, summary_cell_colors)
        reading_info = self._resolve_reading(table_options, table_stats, table_key)
        if isinstance(reading_info, str):
            return reading_info
        reading, aggregation, threshold_value, threshold_units = reading_info
        unit_type = self._reading_unit(reading, table_key, table_options['obs_type'])
        format_string = '%d' if unit_type is None or aggregation else reading.formatter.unit_format_dict[unit_type]
        data_table["settings"]["format_string"] = format_string
        data_table["header_text"] = table_options.get("header_text", table_key + '_tableheader_text')
        populated = self._populate_table_years(data_table, table_options, table_stats, binding, reading, unit_type,
                                               aggregation, threshold_value, threshold_units, table_key)
        if not populated:
            return
        self.aggregations(data_table, table_options['aggregate_type'])

    @staticmethod
    def _set_table_settings(data_table, table_options, table_key, cell_colors, summary_cell_colors):
        settings = data_table["settings"]
        settings["summary_column"] = weeutil.weeutil.to_bool(table_options.get("summary_column", False))
        settings["alltime_min"] = weeutil.weeutil.to_bool(table_options.get("alltime_min", False))
        settings["alltime_avg"] = weeutil.weeutil.to_bool(table_options.get("alltime_avg", False))
        settings["alltime_max"] = weeutil.weeutil.to_bool(table_options.get("alltime_max", False))
        table_name = table_key + '_table'
        settings["table_name"] = table_name
        if None is cell_colors:
            log.warning("Cell colors are not defined for [HistoryReport][[%s]]" % table_key)
        if None is summary_cell_colors:
            summary_cell_colors = cell_colors

    def _resolve_reading(self, table_options, table_stats, table_key):
        obs_type = table_options['obs_type']
        aggregate_type = table_options['aggregate_type']
        reading_binder = getattr(table_stats, obs_type)
        if aggregate_type not in ['max_ge', 'max_le', 'min_ge', 'min_le',
                                  'sum_ge', 'sum_le', 'avg_ge', 'avg_le', 'avg_gt', 'avg_lt']:
            return self._resolve_simple_reading(reading_binder, aggregate_type, table_key)
        return self._resolve_threshold_reading(reading_binder, aggregate_type, table_options, table_key, obs_type)

    @staticmethod
    def _resolve_simple_reading(reading_binder, aggregate_type, table_key):
        try:
            return getattr(reading_binder, aggregate_type), False, None, None
        except KeyError:
            log.info("%s: aggregate_type %s not found" % (os.path.basename(__file__), aggregate_type))
            return TABLE_GENERATION_ERROR % table_key

    @staticmethod
    def _resolve_threshold_reading(reading_binder, aggregate_type, table_options, table_key, obs_type):
        try:
            threshold_value = float(table_options['aggregate_threshold'][0])
        except KeyError:
            log.info("%s: Problem with aggregate_threshold. Should be in the format: [value], [units]" %
                     os.path.basename(__file__))
            return TABLE_GENERATION_ERROR % table_key
        threshold_units = table_options['aggregate_threshold'][1]
        try:
            reading = getattr(reading_binder, aggregate_type)(
                (threshold_value, threshold_units, weewx.units.obs_group_dict[obs_type]))
        except IndexError:
            log.info("%s: Problem with aggregate_threshold units: %s" %
                     (os.path.basename(__file__), str(threshold_units)))
            return TABLE_GENERATION_ERROR % table_key
        return reading, True, threshold_value, threshold_units

    @staticmethod
    def _reading_unit(reading, table_key, obs_type):
        try:
            return reading.converter.group_unit_dict[reading.value_t[2]]
        except KeyError:
            log.info("%s: obs_type %s no unit found" % (os.path.basename(__file__), obs_type))
            return None

    def _populate_table_years(self, data_table, table_options, table_stats, binding, reading, unit_type,
                              aggregation, threshold_value, threshold_units, table_key):
        aggregate_type = table_options['aggregate_type']
        converter = table_stats.converter
        obs_type = table_options['obs_type']
        startdate = table_options.get('startdate')
        for year in table_stats.years():
            if 'units' in table_options:
                unit_formatted = table_options['units']
            elif unit_type in reading.formatter.unit_label_dict:
                unit_formatted = reading.formatter.unit_label_dict[unit_type]
            else:
                unit_formatted = ""
            data_table["unit"] = unit_formatted
            year_data = self._new_year_data(year)
            for month in year.months():
                obs_month = getattr(month, obs_type)
                obs_month.data_binding = binding
                value = self._month_value(obs_month, month, startdate, reading, unit_type, converter,
                                          aggregate_type, aggregation, threshold_value, threshold_units,
                                          obs_type, table_key)
                if value is None:
                    return False
                year_data['values'].append({"value": value, "covers_timespan": self.covers_timespan(month)})
            obs_year = getattr(year, obs_type)
            obs_year.data_binding = binding
            value = self._year_value(obs_year, aggregate_type, aggregation, threshold_value, threshold_units,
                                     obs_type, converter)
            year_data["summary"] = {"value": value, "covers_timespan": self.covers_timespan(year)}
            data_table["year"].append(year_data)
        return True

    @staticmethod
    def _new_year_data(year):
        return {"head": {"value": str(datetime.fromtimestamp(year.timespan[0]).year)},
                "values": [], "sum": None, "count": 0, "min": None, "max": None, "avg": None}

    def _month_value(self, obs_month, month, startdate, reading, unit_type, converter, aggregate_type,
                     aggregation, threshold_value, threshold_units, obs_type, table_key):
        if startdate is not None and month.timespan.start < int(startdate):
            return weewx.units.ValueTuple(None, reading.value_t.unit, reading.value_t.group)
        if aggregation:
            return self.getCount(obs_month, aggregate_type, threshold_value, threshold_units, obs_type)
        if unit_type is not None:
            return converter.convert(getattr(obs_month, aggregate_type).value_t)
        log.error("Error in [HistoryReport][[%s]]: check units" % table_key)
        return None

    def _year_value(self, obs_year, aggregate_type, aggregation, threshold_value, threshold_units,
                    obs_type, converter):
        if aggregation:
            return self.getCount(obs_year, aggregate_type, threshold_value, threshold_units, obs_type)
        return converter.convert(getattr(obs_year, aggregate_type).value_t)
    
    def covers_timespan(self, period):
        return period.timespan.start >= self.alltime_timespan.start and period.timespan.stop <= self.alltime_timespan.stop
    
    def aggregations(self, data_table, aggregate_type):
        if not self.check_aggregations(data_table):
            return
        summary_entry = self.init_entry(data_table)
        aggregations = {"head": aggregate_type, "values": [], "summary": summary_entry}
        data_table["aggregations"] = aggregations
        for year in data_table["year"]:
            self.aggregate_months(year, aggregations, aggregate_type, data_table)
            
            value = year["summary"]["value"]
            self.aggregate_period(value, summary_entry, aggregate_type, year["summary"]["covers_timespan"])

        for month_entry in aggregations["values"]:
            if "avg" in month_entry and month_entry["count"] > 0:
                month_entry["avg"] = self.get_avg_as_value_tuple(month_entry)
        
        if "avg" in summary_entry and summary_entry["count"] > 0:
            summary_entry["avg"] =  self.get_avg_as_value_tuple(summary_entry)
    
    def get_avg_as_value_tuple(self, entry):
        return weewx.units.ValueTuple(entry["sum"].value / entry["count"], entry["sum"].unit, entry["sum"].group)
    
    def check_aggregations(self, data_table):
        return data_table["settings"]["alltime_min"] or data_table["settings"]["alltime_avg"] or data_table["settings"]["alltime_max"]

    def init_entry(self, data_table):
        entry = {"sum": None, "count": 0}
        if data_table["settings"]["alltime_min"]:
            entry.update({"min": None})
        if data_table["settings"]["alltime_avg"]:
            entry.update({"avg": None})
        if data_table["settings"]["alltime_max"]:
            entry.update({"max": None})
        return entry

    def aggregate_months(self, year, aggregations, aggregate_type, data_table):
        for index, month in enumerate(year["values"]):
            if len(aggregations["values"]) <= index:
                month_entry = self.init_entry(data_table)
                aggregations["values"].append(month_entry)
            else:
                month_entry = aggregations["values"][index]
            value = month["value"]
            self.aggregate_period(value, month_entry, aggregate_type, month["covers_timespan"])

    def aggregate_period(self, value, period_entry, aggregate_type, covers_timespan):
        if value.value is None:
            return
        if covers_timespan:
            self._aggregate_complete_period(value, period_entry)
        else:
            self._aggregate_partial_period(value, period_entry, aggregate_type)

    @staticmethod
    def _aggregate_complete_period(value, period_entry):
        period_entry["count"] += 1
        if period_entry["sum"] is not None:
            period_entry["sum"] += value
        else:
            period_entry["sum"] = value
        if "min" in period_entry and (period_entry["min"] is None or value < period_entry["min"]):
            period_entry["min"] = value
        if "max" in period_entry and (period_entry["max"] is None or value > period_entry["max"]):
            period_entry["max"] = value

    @staticmethod
    def _aggregate_partial_period(value, period_entry, aggregate_type):
        if "min" in period_entry and aggregate_type == "min" and (
                period_entry["min"] is None or value < period_entry["min"]):
            period_entry["min"] = value
        if "max" in period_entry and (aggregate_type == "max" or value.unit == 'count') and (
                period_entry["max"] is None or value > period_entry["max"]):
            period_entry["max"] = value

    def _statsDictNOAA(self, data_table, table_options, table_stats):
        """
        table_options: Dictionary containing skin.conf options for particluar table
        all_stats: Link to all_stats TimespanBinder
        """
        data_table["header_text"] = "NOAA_tableheader_text"
        data_table["settings"]["noaa"] = True

        for year in table_stats.years():
            year_number = datetime.fromtimestamp(year.timespan[0]).year
            value = {"value": str(year_number)}
            
            dt = datetime.fromtimestamp(year.timespan[0])
            value["url"] = dt.strftime(table_options['year_filename'])
            year_data = {"head": value, "values": [], "sum": 0, "count": 0, "min": None, "max": None}

            for month in year.months():
                noaa_value = {"value": ""}
                if (month.timespan[1] >= table_stats.timespan.start) and (month.timespan[0] <= table_stats.timespan.stop):
                    dt = datetime.fromtimestamp(month.timespan[0])
                    noaa_value["value"] = dt.strftime("%m-%y")
                    noaa_value["url"] = dt.strftime(table_options['month_filename'])
                year_data["values"].append(noaa_value)           
                year_data["summary"] = value

            data_table["year"].append(year_data)

    def getCount(self, obs_period, aggregate_type, threshold_value, threshold_units, obs_type):
        try:
            return getattr(obs_period, aggregate_type)((threshold_value, threshold_units, weewx.units.obs_group_dict[obs_type])).value_t
        except Exception:
            return [0, 'count']
    
    def last_mtime_resources(self, type, weewx_root, html_root):
        if not os.path.isabs(html_root):
            html_root = os.path.join(weewx_root, html_root)
        resource_path = os.path.join(html_root, type)
        last_mtime = 0
        if os.path.exists(resource_path):
            for fname in os.listdir(resource_path):
                if fname.endswith(type) and  os.path.getmtime(os.path.join(resource_path, fname)) > last_mtime:
                    last_mtime = os.path.getmtime(os.path.join(resource_path, fname))
        else:
            log.debug("Couldn't open %s, using version instead" % resource_path)
            return self.search_list_extension['fuzzy_archer_version']
        return str(math.floor(last_mtime))


class FormatCell(SearchList):
    def format_cell(self, value, table_settings, summary=False):

        background_color = "#ffffff"
        font_color = "#000000"

        if value is None:
            return {"formatted_value": None, "font_color": font_color, "background_color": background_color}

        value_vh = weewx.units.ValueHelper(value)
        value_vt = value_vh.value_t

        formatted_value = value_vh.format(table_settings["format_string"], "-")

        colors_key = table_settings["table_options"]["obs_type"]
        if "colors" in table_settings["table_options"]:
            colors_key = table_settings["table_options"]["colors"][0]

        if value_vt.value is None or colors_key not in table_settings["color_dict"] or value_vt.unit != 'count' and value_vt.unit not in table_settings["color_dict"][colors_key]:
            return {"formatted_value": formatted_value, "font_color": font_color, "background_color": background_color}
        
        config = table_settings["color_dict"][colors_key][value_vt.unit]

        try:
            color_definition = config['minvalues']

            if summary and 'summary' in config:
                color_definition = config['summary']['minvalues']

            for index, lower_bound in enumerate(color_definition):
                if value_vt.value >= float(lower_bound) and ((index + 1) >= len(color_definition) or value_vt.value < float(color_definition[index + 1])):
                    return {"formatted_value": formatted_value, "font_color": config['fontColors'][index], "background_color": config['colors'][index]}
        except KeyError:
            log.info("%s: error reading color configuration for [HistoryReport][[%s]][[[%s]]]" % (os.path.basename(__file__), colors_key, value_vt.unit))

        return {"formatted_value": formatted_value, "font_color": font_color, "background_color": background_color}