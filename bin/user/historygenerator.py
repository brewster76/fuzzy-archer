#
# Copyright (c) 2013-2016  Nick Dajda <nick.dajda@gmail.com>
#
# Distributed under the terms of the GNU GENERAL PUBLIC LICENSE
#
"""Extends the Cheetah generator search list to add html historic data tables in a nice color scheme.

Tested on Weewx release 5.1.0.
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
import hashlib

try:
    from weeutil.weeutil import accumulateLeaves
except:
    from weeutil.config import accumulateLeaves
from weewx.cheetahgenerator import SearchList
from weewx.tags import TimespanBinder

log = logging.getLogger(__name__)

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
        self.search_list_extension['fuzzy_archer_version'] = generator.skin_dict['version']  
        self.search_list_extension['css_hash'] = self.hash_resource('css', generator.skin_dict['HTML_ROOT'])
        self.search_list_extension['js_hash'] = self.hash_resource('js', generator.skin_dict['HTML_ROOT'])

        # Make some config available to templates
        self.add_to_extension_list('Navigation', generator.skin_dict)
        self.add_to_extension_list('StationInfo', generator.skin_dict)
        self.add_to_extension_list('TranslationLinks', generator.skin_dict)
        self.add_to_extension_list('HistoryReport', generator.skin_dict)
        self.add_to_extension_list('ImageGenerator', generator.skin_dict)
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

        # Time to recalculate?
        if (time.time() - (self.refresh_interval * 60)) > self.cache_time:
            self.cache_time = time.time()

            #
            #  The html history tables
            #

            t1 = time.time()
            ngen = 0
            self.search_list_extension["history_tables"] = {}

            for table_key in self.table_dict.sections:

                table_options = accumulateLeaves(self.table_dict[table_key])

                # Get the binding where the data is allocated
                binding = table_options.get('data_binding', 'wx_binding')

                #
                # The all time statistics
                #

                # If this generator has been called in the [SummaryByMonth] or [SummaryByYear]
                # section in skin.conf then valid_timespan won't contain enough history data for
                # the colorful summary tables. Use the data binding provided as table option.
                self.alltime_timespan = weeutil.weeutil.TimeSpan(db_lookup(data_binding=binding).first_timestamp, db_lookup(data_binding=binding).last_timestamp)


                # First, get a TimeSpanStats object for all time. This one is easy
                # because the object valid_timespan already holds all valid times to be
                # used in the report. se the data binding provided as table option.
                all_stats = TimespanBinder(self.alltime_timespan, db_lookup, data_binding=binding, formatter=self.generator.formatter,
                                           converter=self.generator.converter)

                # Now create a small dictionary with keys 'alltime' and 'seven_day':
                self.search_list_extension['alltime'] = all_stats

                # Show all time unless starting date specified
                startdate = table_options.get('startdate', None)
                if startdate is not None:
                    startdate = weeutil.weeutil.startOfDay(int(startdate))
                    table_timespan = weeutil.weeutil.TimeSpan(int(startdate), db_lookup(binding).last_timestamp)
                    table_stats = TimespanBinder(table_timespan, db_lookup, data_binding=binding, formatter=self.generator.formatter,
                                                 converter=self.generator.converter)
                else:
                    table_stats = all_stats

                new_table = {
                    "year": [],
                    "settings": {"table_options": table_options, "color_dict": self.color_dict}
                }

                self._statsDict(table_key, new_table, table_options, table_stats, binding)
                self.search_list_extension["history_tables"][table_key] = new_table
                ngen += 1

            t2 = time.time()

            log.info("%s: Generated %d tables in %.2f seconds" %
                     (os.path.basename(__file__), ngen, t2 - t1))

        return [self.search_list_extension]

    def _parseTableOptions(self, table_options, table_key):
        if table_key == 'NOAA':
            return 'NOAA', None

        obs_type = table_options.get('obs_type')
        colors_key = obs_type

        unit = self.units_dict["Groups"][weewx.units.obs_group_dict[obs_type]]
        if "colors" in table_options:
            colors_key = table_options.get("colors")[0]
            unit = table_options.get("colors")[1]

        if colors_key in self.color_dict and unit in self.color_dict[colors_key]:
            table_colors = self.color_dict[colors_key][unit]
        else:
            log.info("No colors defined for [HistoryReport][[%s]]" % table_key)
            table_colors = {"minvalues": [0], "colors": ["#ffffff"]}

        # Check everything's the same length
        l = len(table_colors['minvalues'])

        for i in [table_colors['minvalues'], table_colors['colors']]:
            if len(i) != l:
                log.info("%s: minvalues and colors must have the same number of elements in [HistoryReport][[%s]]"
                         % (os.path.basename(__file__), table_key))
                return None, None

        summary_colors = None
        if colors_key in self.color_dict and unit in self.color_dict[colors_key] and "summary" in self.color_dict[colors_key][unit]:
            summary_colors = self.color_dict[colors_key][unit]["summary"]

            # Check everything's the same length
            l = len(summary_colors['minvalues'])

            for i in [summary_colors['minvalues'], summary_colors['colors']]:
                if len(i) != l:
                    log.info("%s: minvalues and colors must have the same number of elements in [HistoryReport][[%s]][summary]"
                             % (os.path.basename(__file__), table_key))
                    return None, None

        font_color_list = table_colors['fontColors'] if 'fontColors' in table_colors else ['#000000'] * l
        cell_colors = list(zip(table_colors['minvalues'], table_colors['colors'], font_color_list))

        summary_cell_colors = None
        if None is not summary_colors:
            font_color_list = summary_colors['fontColors'] if 'fontColors' in summary_colors else ['#000000'] * l
            summary_cell_colors = list(zip(summary_colors['minvalues'], summary_colors['colors'], font_color_list))

        return cell_colors, summary_cell_colors

    def _statsDict(self, table_key, data_table, table_options, table_stats, binding):
        """
        table_options: Dictionary containing skin.conf options for particluar table
        all_stats: Link to all_stats TimespanBinder
        """
        
        if table_key == 'NOAA':
            return self._statsDictNOAA(data_table, table_options, table_stats)

        cell_colors, summary_cell_colors = self._parseTableOptions(table_options, table_key)
        data_table["settings"]["summary_column"] = weeutil.weeutil.to_bool(table_options.get("summary_column", False))
        data_table["settings"]["alltime_min"] = weeutil.weeutil.to_bool(table_options.get("alltime_min", False))
        data_table["settings"]["alltime_avg"] = weeutil.weeutil.to_bool(table_options.get("alltime_avg", False))
        data_table["settings"]["alltime_max"] = weeutil.weeutil.to_bool(table_options.get("alltime_max", False))
        table_name = table_key + '_table'
        data_table["settings"]["table_name"] = table_name

        if None is cell_colors:
            log.warning("Cell colors are not defined for [HistoryReport][[%s]]" % table_key)

        if None is summary_cell_colors:
            summary_cell_colors = cell_colors

        unit_formatted = ""
        unit_type = None
        format_string = None

        obs_type = table_options['obs_type']
        aggregate_type = table_options['aggregate_type']
        converter = table_stats.converter

        # obs_type
        reading_binder = getattr(table_stats, obs_type)
        aggregation = False
        # Some aggregate come with an argument
        if aggregate_type in ['max_ge', 'max_le', 'min_ge', 'min_le',
                                'sum_ge', 'sum_le', 'avg_ge', 'avg_le',
                                'avg_gt', 'avg_lt']:
            aggregation = True
            try:
                threshold_value = float(table_options['aggregate_threshold'][0])
            except KeyError:
                log.info("%s: Problem with aggregate_threshold. Should be in the format: [value], [units]" %
                            (os.path.basename(__file__)))
                return "Could not generate table [HistoryReport][[%s]]" % table_key

            threshold_units = table_options['aggregate_threshold'][1]

            try:
                reading = getattr(reading_binder, aggregate_type)((threshold_value, threshold_units, weewx.units.obs_group_dict[obs_type]))
            except IndexError:
                log.info("%s: Problem with aggregate_threshold units: %s" % (os.path.basename(__file__),
                                                                                str(threshold_units)))
                return "Could not generate table [HistoryReport][[%s]]" % table_key
        else:
            try:
                reading = getattr(reading_binder, aggregate_type)
            except KeyError:
                log.info("%s: aggregate_type %s not found" % (os.path.basename(__file__),
                                                                aggregate_type))
                return "Could not generate table [HistoryReport][[%s]]" % table_key

        try:
            unit_type = reading.converter.group_unit_dict[reading.value_t[2]]
        except KeyError:
            log.info("%s: obs_type %s no unit found" % (os.path.basename(__file__),
                                                        obs_type))

        # For aggregrate types which return number of occurrences (e.g. max_ge), set format to integer

        # Don't catch error here - we absolutely need the string format
        if None is unit_type or aggregation:
            format_string = '%d'
        else:
            format_string = reading.formatter.unit_format_dict[unit_type]

        data_table["settings"]["format_string"] = format_string

        header_text = table_name + "header_text"

        if "header_text" in table_options:
            header_text = table_options["header_text"]

        data_table["header_text"] = header_text

        for year in table_stats.years():
            # 'units' option in skin.conf?
            if 'units' in table_options:
                unit_formatted = table_options['units']
            else:
                if unit_type in reading.formatter.unit_label_dict:
                    unit_formatted = reading.formatter.unit_label_dict[unit_type]

            data_table["unit"] = unit_formatted

            year_data = {"head": {"value": str(datetime.fromtimestamp(year.timespan[0]).year)}, 
                        "values": [],
                        "sum": None,
                        "count": 0,
                        "min": None,
                        "max": None,
                        "avg": None
                        }

            for month in year.months():
                # update the binding to access the right DB
                obs_month = getattr(month, obs_type)
                obs_month.data_binding = binding
                if aggregation:
                    value = self.getCount(obs_month, aggregate_type, threshold_value, threshold_units, obs_type)
                elif unit_type is not None:
                    value = converter.convert(getattr(obs_month, aggregate_type).value_t)
                else:
                    log.error("Error in [HistoryReport][[%s]]: check units" % table_key)
                    return

                year_data['values'].append({"value": value, "covers_timespan": self.covers_timespan(month)})
        
                obs_year = getattr(year, obs_type)
                obs_year.data_binding = binding
            
            if aggregation:
                value = self.getCount(obs_year, aggregate_type, threshold_value, threshold_units, obs_type)
            else:
                value = converter.convert(getattr(obs_year, aggregate_type).value_t)
            year_data["summary"] = {"value": value, "covers_timespan": self.covers_timespan(year)}

            data_table["year"].append(year_data)

        self.aggregations(data_table, aggregate_type)
    
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
            period_entry["count"] += 1
            if period_entry["sum"] is not None:
                period_entry["sum"] += value
            else:
                period_entry["sum"] = value
            if "min" in period_entry and (period_entry["min"] is None or value < period_entry["min"]):
                period_entry["min"] = value
            if "max" in period_entry and (period_entry["max"] is None or value > period_entry["max"]):
                period_entry["max"] = value
        else:
            if "min" in period_entry and (aggregate_type == "min" and (period_entry["min"] is None or value < period_entry["min"])):
                period_entry["min"] = value
            if "max" in period_entry and (aggregate_type == "max" and (period_entry["max"] is None or value > period_entry["max"])):
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
        except:
            return [0, 'count']
    
    def hash_resource(self, type, html_root):
        resource_path = os.path.join(html_root, type)
        hash_value = ""
        if os.path.exists(resource_path):
            for fname in os.listdir(resource_path):
                if fname.endswith(type):
                    with open(os.path.join(resource_path, fname), "rb") as f:
                        file_hash = hashlib.sha1()
                        while chunk := f.read(8192):
                            file_hash.update(chunk)
                    hash_value += file_hash.hexdigest()
            hash_value = hash(hash_value)
        else:
            hash_value = self.search_list_extension['fuzzy_archer_version']
        return hash_value


class FormatCell(SearchList):
    def format_cell(self, value, table_settings, summary=False):

        value_vh = weewx.units.ValueHelper(value)
        background_color = "#ffffff"
        font_color = "#000000"

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