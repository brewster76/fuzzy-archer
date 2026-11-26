# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
#    Author: Michael Kainzbauer (github: mkainzbauer)
"""generator for configuration and initializing live data skin

Tested with sqlite, may not work with other databases.

Directions for use:

1) Put this file in the weewx/bin/user directory.
2) Add user.jsonengine.JSONGenerator to the list of Generators in skin.conf.
3) Add a [JSONGenerator] section to skin.conf.
   Any data contained in this section are created when the report generator
   runs.
4) Object member names must match the Weewx field name, e.g. outTemp or barometer
5) Here is an example [JSONGenerator] section:

############################################################################################
#
# Settings for JSON Generator
#
TODO: example
"""
import sys
import logging
import json
import configobj
import os.path
import zoneinfo

import weewx.reportengine
import weewx.xtypes

try:
    from weeutil.weeutil import accumulateLeaves
except ImportError:
    from weeutil.config import accumulateLeaves
from weeutil.config import merge_config
from weewx.units import convert
from weeutil.weeutil import to_bool
from weeutil.weeutil import TimeSpan
from datetime import datetime, time, timedelta
from user.sunevents import compute_sun_events

try:
    from tzlocal import get_localzone_name
except ImportError:
    get_localzone_name = None

log = logging.getLogger(__name__)

def live_gauge_data_items(gauge_dict):
    """Return configured gauges plus observations required by the optional wind radar."""
    items = gauge_dict.get('live_gauge_items', [])
    if isinstance(items, str):
        items = [item.strip() for item in items.split(',') if item.strip()]
    items = list(items or [])
    wind_radar = gauge_dict.get('wind_radar', {})
    if to_bool(wind_radar.get('enabled', False)):
        for observation in ('windDir', 'windSpeed', 'windGust'):
            if observation not in items:
                items.append(observation)
    return items

class JSONGenerator(weewx.reportengine.ReportGenerator):
    """Class for managing the JSON generator."""

    def run(self):
        enabled = False
        try:
            enabled = self.skin_dict['JSONGenerator']['enabled'].lower() == 'true'
        except KeyError:
            log.info("JSONGenerator failed to read config or config missing")
        else:
            if enabled:
                if self.setup():
                    self.gen_data()
            else:
                log.info("JSONGenerator is not enabled")
    def setup(self):
        self.json_dict = self.skin_dict['JSONGenerator']
        self.gauge_dict = self.skin_dict['LiveGauges']
        self.chart_dict = self.skin_dict['LiveCharts']
        self.units_dict = self.skin_dict['Units']
        try:
            merge_config(self.units_dict, self.config_dict['StdReport']['Defaults']['Units'])
        except KeyError as keyError:
            log.debug("JSONGenerator: Could not merge ['StdReport']['Defaults']['Units'] because '%s' is missing" % keyError.args[0])
        
        self.labels_dict = self.skin_dict['Labels']
        try:
            merge_config(self.labels_dict, self.config_dict['StdReport']['Defaults']['Labels'])
        except KeyError as keyError:
            log.debug("JSONGenerator: Could not merge ['StdReport']['Defaults']['Labels'] because '%s' is missing" % keyError.args[0])
        
        self.frontend_data = {}

        # Create a converter to get this into the desired units
        self.converter = weewx.units.Converter(self.units_dict['Groups'])

        # Lookup the last reading in the archive
        db_manager = self.db_binder.get_manager()
        self.lastGoodStamp = db_manager.lastGoodStamp()
        if self.lastGoodStamp is None:
            log.info("JSONGenerator: the database contains no archive records yet, nothing to generate")
            return False

        self.record_dict_vtd = None
        batch_records = db_manager.genBatchRecords(self.lastGoodStamp - 1, self.lastGoodStamp)

        self.transition_angle = 8
        try:
            self.transition_angle = int(self.chart_dict['transition_angle'])
        except KeyError:
            log.debug('Using default transition_angle %s' % self.transition_angle)

        self.show_daynight = True
        try:
            self.show_daynight = to_bool(self.chart_dict['show_daynight'])
        except KeyError:
            log.debug('show_daynight is on')

        try:
            for rec in batch_records:
                if self.record_dict_vtd is None:
                    self.record_dict_vtd = rec

        except Exception:
            log.info("JSONGenerator: Cannot find the current reading")

        # For checking development code deals with 'None' readings correctly
        if self.gauge_dict.get('test_none_readings', None) is not None:
            for key in self.record_dict_vtd:
                self.record_dict_vtd[key] = None
        return True

    def gen_data(self):
        start_time = datetime.now().timestamp()
        ngen = 0
        unit_systems = {'US': weewx.units.USUnits, 'METRIC': weewx.units.MetricUnits, 'METRICWX': weewx.units.MetricWXUnits}
        source_unit_system = self.config_dict['StdConvert']['target_unit']

        self.frontend_data['config'] = self.json_dict
        self.frontend_data['config']['archive_interval'] = self.config_dict['StdArchive']['archive_interval']
        self.frontend_data['config']['station_timezone'] = self.get_station_timezone()

        self.frontend_data['gauges'] = self.gauge_dict
        self.frontend_data['charts'] = self.chart_dict
        self.frontend_data['source_unit_system'] = {'type': source_unit_system}
        for unit_system_item in unit_systems[source_unit_system].items():
            self.frontend_data['source_unit_system'][unit_system_item[0]] = unit_system_item[1]
        self.frontend_data['units'] = self.units_dict
        self.frontend_data['labels'] = self.labels_dict
        self.add_period_data()
        live_options = accumulateLeaves(self.json_dict)
        duration = int(live_options.get('timespan'))
        first_value_timestamp = self.lastGoodStamp - duration * 60 * 60
        last_value_timestamp = self.lastGoodStamp
        self.first_timestamp = first_value_timestamp

        for chart in self.chart_dict.sections:
            if chart not in self.chart_dict["live_chart_items"]:
                continue
            for category in self.chart_dict[chart].sections:
                category_config = self.frontend_data['charts'][chart][category]
                ret, category_history, daily_highlow_values = self.gen_history_data(category, category_config, self.chart_dict[chart][category].get('data_binding'))
                category_config['target_unit'] = self.get_target_unit(category)
                category_config['obs_group'] = self.get_obs_group(category)

                if ret is not None:
                    ngen += 1
                    log.debug("Adding %s to frontend_data." % category)
                    self.frontend_data[category] = category_history
                    self.frontend_data[category + "_daily_high_low"] = daily_highlow_values
        gauge_data_items = live_gauge_data_items(self.gauge_dict)
        for gauge in self.gauge_dict.sections:
            if gauge == 'wind_radar':
                continue
            if gauge not in gauge_data_items:
                continue
            gauge_config = self.frontend_data['gauges'][gauge]
            ret, gauge_history, _ = self.gen_history_data(gauge, gauge_config, self.gauge_dict[gauge].get('data_binding'))
            gauge_config['target_unit'] = self.get_target_unit(gauge)
            gauge_config['obs_group'] = self.get_obs_group(gauge)

            if ret is not None:
                ngen += 1
                log.debug("Adding %s to frontend_data." % gauge)
                self.frontend_data[gauge] = gauge_history

        altitude_m = convert(self.stn_info.altitude_vt, 'meter')[0]
        events = self.get_day_night_events(first_value_timestamp, last_value_timestamp, self.stn_info.longitude_f, self.stn_info.latitude_f, altitude_m)
        self.frontend_data['day_night_events'] = events

        # Write JSON self.frontend_data output if a filename is specified
        data_filename = 'weewxData.json'
        timestamp_filename = 'ts.json'
        html_root = os.path.join(self.config_dict['WEEWX_ROOT'], live_options['HTML_ROOT'])

        if not os.path.exists(html_root):
            os.makedirs(html_root)
        self.write_json(os.path.join(html_root, data_filename))
        self.write_ts_file(os.path.join(html_root, timestamp_filename))

        finish_time = datetime.now().timestamp()

        log.info("JSONGenerator: Generated %d data items for %s in %.2f seconds" %
                 (ngen, self.skin_dict['REPORT_NAME'], finish_time - start_time))

    def add_period_data(self):
        """Additive keys for the Day/Week/Month/Year views (docs/historic-data-contract.md, section 8).
        Never affects the Live data: errors are logged and the keys omitted."""
        section = self.skin_dict.get('PeriodCharts')
        if not section:
            return
        try:
            from user.historyconfig import PeriodChartsConfig, frontend_charts, frontend_config, period_titles
            from user.historydata import resolve_week_start
            config = PeriodChartsConfig(section, self.skin_dict.get('data_binding', 'wx_binding'))
            groups = self.units_dict.get('Groups', {})
            self.frontend_data['period_charts'] = frontend_charts(
                config, lambda data_type: weewx.units.obs_group_dict.get(data_type, ''),
                lambda group: groups.get(group, ''), self.labels_dict.get('Generic', {}))
            self.frontend_data['period_config'] = frontend_config(
                config, resolve_week_start(self.config_dict, self.stn_info),
                self.config_dict['StdArchive']['archive_interval'])
            self.frontend_data['period_titles'] = period_titles(self.units_dict.get('TimeFormats', {}))
        except Exception:
            log.exception("JSONGenerator: could not add period view configuration")
            for key in ('period_charts', 'period_config', 'period_titles'):
                self.frontend_data.pop(key, None)

    def get_target_unit(self, column_name):
        try:
            return self.units_dict['Groups'][weewx.units.obs_group_dict[column_name]]
        except KeyError:
            log.info("JSONGenerator: self.units_dict['Groups'][weewx.units.obs_group_dict['%s']] is not present, using the empty string." % column_name)
            return ""

    def get_obs_group(self, column_name):
        try:
            return weewx.units.obs_group_dict[column_name]
        except KeyError:
            log.info("JSONGenerator: weewx.units.obs_group_dict['%s'] is not present, using the empty string." % column_name)
            return ""

    def gen_history_data(self, obs_name, item_config, binding_name):

        column_name = item_config.get('data_type', obs_name)
        log.debug("Generating history for obs_name %s and column_name %s with binding %s" % (obs_name, column_name, binding_name))

        if obs_name in self.frontend_data:
            log.debug("Data for observation %s has already been collected." % obs_name)
            return None, None, None
        else:
            try:
                if binding_name:
                    db_manager = self.db_binder.get_manager(binding_name)
                else:
                    db_manager = self.db_binder.get_manager()
            except Exception:
                if binding_name:
                    log.exception("Could not get db_manager for binding %s", binding_name)
                else:
                    log.exception("Could not get db_manager for default binding")
                return 0, None, None

        # Find display unit of measure
        target_unit = self.get_target_unit(column_name)

        aggregate_types = []
        if item_config.get('showMaxMarkPoint', 'false') == 'true':
            aggregate_types.append("max")
        if item_config.get('showMinMarkPoint', 'false') == 'true':
            aggregate_types.append("min")

        timespan = TimeSpan(self.first_timestamp, self.lastGoodStamp)
        try:
            series = weewx.xtypes.get_series(column_name, timespan, db_manager)
            daily_highlow_values = []
            for aggregate_type in aggregate_types:
                daily_highlow_values.append(self.get_daily_highlow_values(column_name, aggregate_type, self.first_timestamp, self.lastGoodStamp, db_manager))
        except (weewx.UnknownType, weewx.UnknownAggregation) as e:
            log.warning("JSONGenerator: '%s' is not in the database, sending no data for it (%s: %s)"
                        % (column_name, type(e).__name__, e))
            return 1, [], []
        combined_series, processed_highlow_values = self.combine_series(series, daily_highlow_values, item_config, target_unit)
        log.debug("Returning data series for '%s'" % column_name)
        return 1, combined_series, processed_highlow_values

    def write_json(self, data_filename):

        try:
            fp = open(data_filename, 'w')
        except IOError:
            log.error("JSONGenerator: Could not open %s for writing" % data_filename)
        else:
            with fp:
                json_string = json.dumps(self.frontend_data, indent=None)
                fp.write(json_string)

    def write_ts_file(self, timestamp_filename):
        try:
            fp = open(timestamp_filename, 'w')
        except IOError:
            log.error("JSONGenerator: Could not open %s for writing" % timestamp_filename)
        else:
            with fp:
                fp.write('{"lastGoodStamp":"' + str(self.lastGoodStamp) + '"}')


    def get_day_night_events(self, start, end, lon, lat, altitude_m):
        if not self.show_daynight:
            return []

        sqlite_root = self.config_dict.get('DatabaseTypes',configobj.ConfigObj()).get('SQLite',configobj.ConfigObj()).get('SQLITE_ROOT','.')
        path = os.path.join(
            self.config_dict.get('WEEWX_ROOT','.'),
            sqlite_root,
            'skyfield'
        )

        events = compute_sun_events(start, end, lon, lat, int(altitude_m), path,
                                    self.skin_dict['Skyfield']['ephemeris'], self.transition_angle)
        if events is None:
            return []
        
        for event in events:
            event[0] = event[0] * 1000
            angle = event[1]
            darkening_extent = abs(((event[1] - self.transition_angle) / 2) / self.transition_angle)
            if angle >= self.transition_angle:
                darkening_extent = 0
            if angle <= -self.transition_angle:
                darkening_extent = 1
            event[1] = darkening_extent
        return events

    def combine_series(self, series, daily_highlow_values, item_config, target_unit):

        decimals = int(item_config.get('decimals', '3'))
        combined_series = []
        processed_highlow_values = []
        for index, interval_start_time in enumerate(series[0][0]):
            interval_end_time = series[1][0][index]
            value = series[2][0][index]
            if value is not None:
                value = self.convert_value(value, decimals, series[2].unit, series[2].group, target_unit)
            self._append_interval_highlow_values(
                daily_highlow_values, interval_start_time, interval_end_time, decimals,
                series[2].unit, series[2].group, target_unit, combined_series, processed_highlow_values)
            combined_series.append([interval_end_time * 1000, value])
        return combined_series, processed_highlow_values

    def _append_interval_highlow_values(self, daily_highlow_values, interval_start_time, interval_end_time,
                                        decimals, source_unit, source_group, target_unit,
                                        combined_series, processed_highlow_values):
        for highlow_values in daily_highlow_values:
            for highlow_value in highlow_values:
                highlow_time = highlow_value[0]
                if highlow_time is None or highlow_time <= interval_start_time or highlow_time > interval_end_time:
                    continue
                processed_value = [
                    highlow_time * 1000,
                    self.convert_value(highlow_value[1], decimals, source_unit, source_group, target_unit)]
                combined_series.append(processed_value)
                processed_value.append(highlow_value[2])
                processed_highlow_values.append(processed_value)

    def convert_value(self, value, decimals, source_unit, source_group, target_unit):
        if target_unit != "":
            value_tuple = {0: value, 1: source_unit, 2: source_group}
            value = weewx.units.convert(value_tuple, target_unit)[0]

        return round(float(value), decimals + 1)

    def get_daily_highlow_values(self, obs_type, aggregate_type, start_time, end_time, db_manager):
        value_list = []
        start_of_day = datetime.combine(datetime.fromtimestamp(start_time), time.min)
        while start_of_day.timestamp() < end_time:
            start_of_next_day = start_of_day + timedelta(days=1)
            timespan = TimeSpan(start_of_day.timestamp(), start_of_next_day.timestamp())
            highlow_value = weewx.xtypes.get_aggregate(obs_type, timespan, aggregate_type, db_manager)[0]
            highlow_time = weewx.xtypes.get_aggregate(obs_type, timespan, aggregate_type + "time", db_manager)[0]
            value_list.append([highlow_time, highlow_value, aggregate_type])

            start_of_day = start_of_next_day

        return value_list
    
    def get_station_timezone(self):
        station_timezone = None
        if get_localzone_name is not None:
            # return IANA timezone, or fallback, using tzlocal
            # get_localzone_name can raise an exception if TZ environment variable is set to something it does not understand
            try:
                station_timezone = get_localzone_name()
            except zoneinfo.ZoneInfoNotFoundError as err:
                log.debug("tzlocal get_localzone_name execption. Will fallback to UTC offset: %s", err)
        else:
            log.warning("tzlocal not installed. Will fallback to UTC offset for station timezone")
        
        if station_timezone is None:
            station_timezone = utc_offset_string(datetime.now().astimezone().utcoffset().total_seconds())
        
        return station_timezone


def utc_offset_string(offset_seconds):
    """'+HH:mm' / '-HH:mm', accepted by Luxon on the frontend as alternative to an IANA timezone."""
    offset_seconds = int(offset_seconds)
    sign = '-' if offset_seconds < 0 else '+'
    hours, minutes = divmod(abs(offset_seconds) // 60, 60)
    return f'{sign}{hours:02d}:{minutes:02d}'
