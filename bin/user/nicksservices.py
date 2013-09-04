#
# Nick's attempt at a custom service
#
# Version 1.1
# 16 Feb 2013
#

import syslog

import weewx.wxengine
import weeutil.weeutil

#===============================================================================
#                    Class realtime
#===============================================================================

class realtime(weewx.wxengine.StdService):
    """Outputs every loop factory to a file for realtime viewing.
    File is overwitten every loop packet."""

    def __init__(self, engine, config_dict):
        super(realtime, self).__init__(engine, config_dict)

        self.bind(weewx.NEW_LOOP_PACKET, self.new_loop_packet)

        self.filename = config_dict['realtime']['filename']
        self.fieldList = config_dict['realtime']['report']

        self.obs_group_dict = weewx.units.obs_group_dict
        self.MetricUnits = weewx.units.MetricUnits
        self.unit_format_dict = weewx.units.default_unit_format_dict
        self.unit_label_dict  = weewx.units.default_unit_label_dict
                
    def new_loop_packet(self, event):
        f = open(self.filename, 'w')
    
        f.write ("       Realtime weather information\n")
        f.write ("       ============================\n")
        f.write ("%15s : %s\n" % ("Time", weeutil.weeutil.timestamp_to_string(event.packet['dateTime'])))
        
        for field in self.fieldList:
            obs_group = self.obs_group_dict.get(field)
            unit_label = self.MetricUnits.get(obs_group)
            if None == event.packet[field]:
                val_string = "-"
            else:
                val_string = self.unit_format_dict[unit_label] % event.packet[field]

            val_string += self.unit_label_dict.get(unit_label)

            f.write("%15s: %s\n" % (field, val_string))
        
#        """Print out the new LOOP packet"""
#        syslog.syslog(syslog.LOG_DEBUG, "realtime: LOOP: created %s" % self.filename)

