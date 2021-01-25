# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
#    Author: Michael Kainzbauer (github: mkainzbauer)
"""generator for configuration and initializing live data skin

Tested on Weewx release 4.3.0.
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

import time
import logging
import json
import os.path

import weeutil.weeutil
import weewx.reportengine
import weeplot.utilities
import user.gauges

log = logging.getLogger(__name__)

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
                self.setup()
                self.gen_data()
            else:
                log.info("JSONGenerator is not enabled")
    def setup(self):
        self.db_manager = self.db_binder.get_manager()

        self.json_dict = self.skin_dict['JSONGenerator']
        self.gauge_dict = self.skin_dict['LiveGauges']
        self.chart_dict = self.skin_dict['LiveCharts']
        self.units_dict = self.skin_dict['Units']
        self.labels_dict = self.skin_dict['Labels']
        self.frontend_data = {}

        # Create a converter to get this into the desired units
        self.converter = weewx.units.Converter(self.units_dict['Groups'])

        # Lookup the last reading in the archive
        self.lastGoodStamp = self.db_manager.lastGoodStamp()

        self.record_dict_vtd = None
        batch_records = self.db_manager.genBatchRecords(self.lastGoodStamp - 1, self.lastGoodStamp)

        try:
            for rec in batch_records:
                if self.record_dict_vtd is None:
                    self.record_dict_vtd = rec

        except:
            log.info("JSONGenerator: Cannot find the current reading")

        # For checking development code deals with 'None' readings correctly
        if self.gauge_dict.get('test_none_readings', None) is not None:
            for key, value in list(self.record_dict_vtd.items()):
                self.record_dict_vtd[key] = None

    def gen_data(self):
        """Generate data."""
        startTime = time.time()
        ngen = 0
        self.frontend_data['config'] = self.json_dict
        self.frontend_data['config']['archive_interval'] = self.config_dict['StdArchive']['archive_interval']
        self.frontend_data['gauges'] = self.gauge_dict
        self.frontend_data['charts'] = self.chart_dict
        self.frontend_data['units'] = self.units_dict
        self.frontend_data['labels'] = self.labels_dict
        live_options = weeutil.weeutil.accumulateLeaves(self.json_dict)

        for gauge in self.gauge_dict.sections:
            ret, gauge_history = self.gen_history_data(gauge, live_options)
            self.frontend_data['gauges'][gauge]['target_unit'] = self.get_target_unit(gauge)
            self.frontend_data['gauges'][gauge]['obs_group'] = self.get_obs_group(gauge)

            if ret is not None:
                ngen += 1
                self.frontend_data[gauge] = gauge_history
        for chart in self.chart_dict.sections:
            for category in self.chart_dict[chart].sections:
                ret, category_history = self.gen_history_data(category, live_options)
                self.frontend_data['charts'][chart][category]['target_unit'] = self.get_target_unit(category)
                self.frontend_data['charts'][chart][category]['obs_group'] = self.get_obs_group(category)

                if ret is not None:
                    ngen += 1
                    self.frontend_data[category] = category_history

        # Write JSON self.frontend_data output if a filename is specified
        data_filename = live_options.get('frontend_data_json', None)
        html_root = os.path.join(self.config_dict['WEEWX_ROOT'], live_options['HTML_ROOT'])
        if data_filename is not None:
            self.write_json(os.path.join(html_root, data_filename))

        finishTime = time.time()

        log.info("JSONGenerator: Generated %d data items for %s in %.2f seconds" %
                 (ngen, self.skin_dict['REPORT_NAME'], finishTime - startTime))

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


    def gen_history_data(self, column_name, live_options):
        if column_name in self.frontend_data:
            return None, None
        # Find display unit of measure
        try:
            target_unit = self.get_target_unit(column_name)
        except:
            log.info("JSONGenerator: *** Could not find target unit of measure for column '%s' ***" % column_name)
            return 0, None
        try:
            timespan = int(live_options.get('timespan'))
        except:
            logging.exception("Error getting timespan:")
        else:
            history_list = []
            time_list = []

            batch_records = self.db_manager.genBatchRecords(self.lastGoodStamp - timespan * 60 * 60, self.lastGoodStamp)
            for rec in batch_records:
                db_value_tuple = weewx.units.as_value_tuple(rec, column_name)
                if target_unit == "":
                    history_value = rec[column_name]
                else:
                    history_value = weewx.units.convert(db_value_tuple, target_unit)[0]
                try:
                    history_list.append(float(history_value))
                    time_list.append(rec['dateTime'] * 1000)
                except:
                    log.debug("JSONGenerator: Cannot decode reading of '%s' for column '%s'" % (history_value, column_name))

        return 1, list(zip(time_list, history_list))

    def write_json(self, data_filename):

        try:
            fp = open(data_filename, 'w')
        except IOError:
            log.error("JSONGenerator: Could not open %s for writing" % data_filename)
        else:
            with fp:
                json_string = "let weewxData = " + json.dumps(self.frontend_data, indent=None)
                fp.write(json_string)