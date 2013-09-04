#
#    Copyright (c) 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 1124 $
#    $Author: tkeffer $
#    $Date: 2013-03-27 13:00:35 -0700 (Wed, 27 Mar 2013) $
#
"""AirPi driver for the weewx weather system"""

from __future__ import with_statement
import math
import time

# To read NO2 levels from DERFA website
import urllib
import urllib2
import syslog

import weedb
import weeutil.weeutil
import weewx.abstractstation
import weewx.wxformulas

def loader(config_dict, engine):

    # This loader uses a bit of a hack to have the simulator resume at a later
    # time. It's not bad, but I'm not enthusiastic about having special
    # knowledge about the database in a driver, albeit just the loader.
           
    station = AirPi(**config_dict['AirPi'])

    return station
           
class AirPi(weewx.abstractstation.AbstractStation):
    """Station simulator"""
    
    def __init__(self, **stn_dict):
        """Initialize the simulator
        
        NAMED ARGUMENTS:
        
        loop_interval: The time (in seconds) between emitting LOOP packets. [Optional. Default is 2.5]
        
        """

        # Keep track of when the Oxford pollution website was last polled 
        self.NO2Level = None

        self.loop_interval = float(stn_dict.get('loop_interval', 2.5))
        start_ts = self.the_time = self.nextNO2time = time.time()

        # The following doesn't make much meteorological sense, but it is easy to program!
        self.observations = {'outTemp'     : Observation(magnitude=20.0,  average= 50.0, period=24.0, phase_lag=14.0, start=start_ts),
                             'pressure'    : Observation(magnitude=1.0,   average= 30.1, period=48.0, phase_lag= 0.0, start=start_ts),
                             'outHumidity' : Observation(magnitude=10.0,  average=  5.0, period=48.0, phase_lag=24.0, start=start_ts),
                             'radiation'   : Observation(magnitude=360.0, average=180.0, period=48.0, phase_lag= 0.0, start=start_ts),
                             'UV'          : Observation(magnitude=12.0,  average=  6.0, period=48.0, phase_lag=24.0, start=start_ts),
                             'CO'          : Observation(magnitude=360.0, average=180.0, period=48.0, phase_lag= 0.0, start=start_ts)}

    def genLoopPackets(self):

        while True:
            sleep_time = self.the_time + self.loop_interval - time.time()
            if sleep_time > 0: 
                time.sleep(sleep_time)
        
            # Update the simulator clock:
            self.the_time += self.loop_interval
             
            # Because a packet represents the measurements observed over the
            # time interval, we want the measurement values at the middle
            # of the interval.
            avg_time = self.the_time - self.loop_interval/2.0
            
            _packet = {'dateTime': int(self.the_time+0.5),
                       'usUnits' : weewx.US }
            for obs_type in self.observations:
                _packet[obs_type] = self.observations[obs_type].value_at(avg_time)
    
            if (time.time() > self.nextNO2time):
                # Read another NO2 level
               newNO2Level = readNO2Level()

               if newNO2Level is None:
                   # Check again in 5 minutes
                   self.nextNO2time = time.time() + (5 * 60)
               else:
                   _packet['NO2'] = self.NO2Level = newNO2Level
                   self.nextNO2time = time.time() + (60 * 60)

            yield _packet

    def getTime(self):
        return self.the_time
    
    @property
    def hardware_name(self):
        return "AirPi"
        
def readNO2Level():
    """Reads NO2 levels from DERFA website"""

    try:
        aResp = urllib2.urlopen("http://uk-air.defra.gov.uk/latest/currentlevels");
    except:
        syslog.syslog(syslog.LOG_INFO, "readNO2Level - failed at urlopen()")
        return None

    try:
        web_pg = aResp.read();
    except:
        syslog.syslog(syslog.LOG_INFO, "readNO2Level - failed at aResp.readn()")
        return None

    pos = web_pg.find("site_id=OX8")
    newString = web_pg[pos:]

    NO2 = None

    for i in range(6):
        pos = newString.find("<td")
        newString = newString[pos:]

        pos = newString.find(">")
        endPos = newString.find("</td>")

        tableCell = newString[pos+1:endPos]
        newString = newString[endPos:]     

        if  1 == i:
            NO2start = tableCell.find(">")
            NO2end = tableCell.find("nbsp")
            
            try:
                NO2 = int(tableCell[NO2start+1:NO2end-1])
            except:
                syslog.syslog(syslog.LOG_INFO, "readNO2Level - couldn't find anything useful in '%s'" % tableCell)
                NO2 = None

    if NO2 is not None:
        syslog.syslog(syslog.LOG_INFO, "readNO2Level - measured level of %d" % NO2)
 
    return NO2


class Observation(object):
    
    def __init__(self, magnitude=1.0, average=0.0, period=96.0, phase_lag=0.0, start=None):
        """Initialize an observation function.
        
        magnitude: The value at max. The range will be twice this value
        average: The average value, averaged over a full cycle.
        period: The cycle period in hours.
        phase_lag: The number of hours after the start time when the observation hits its max
        start: Time zero for the observation in unix epoch time."""


        #
        # This only gets called once, so use to init sensor
        #

#
# Archive fields we're going to use
#
#                       ('pressure',             'REAL'),  <-- measure in pressure (station pressure). Weewx factors in temperature
#                                                              and altitude to convert to barometer (pressure equivalent at sea level)
#                       ('outTemp',              'REAL'),
#                       ('outHumidity',          'REAL'),
#                       ('radiation',            'REAL'),
#                       ('UV',                   'REAL'),
#                       ('CO',                   'REAL'),
#                       ('NO2',                  'REAL'),


        if not start:
            raise ValueError("No start time specified")
        self.magnitude = magnitude
        self.average   = average
        self.period    = period * 3600.0
        self.phase_lag = phase_lag * 3600.0
        self.start     = start
        
    def value_at(self, time_ts):
        """Return the observation value at the given time.
        
        time_ts: The time in unix epoch time."""

        phase = 2.0 * math.pi * (time_ts - self.start - self.phase_lag) / self.period
        return self.magnitude * math.cos(phase) + self.average
        



# convert ADC values 
    def get_light_level(self):
#result = self.adc.readADC(self.adcPin) + 1
        result = 72

        vout = float(result)/1023 * 3.3
        rs = ((3.3 - vout) / vout) * 5.6
        return abs(rs)

    def get_uv_level(self):
#result = self.adc.readADC(self.adcPin)
        result = 72

        vout = float(result)/1023 * 3.3
        sensorVoltage = vout / 471
        millivolts = sensorVoltage * 1000
        UVI = millivolts * (5.25/20)
        return UVI


#	def get_NO2(self):
#		conversions = [((0,100),(0,0.25)),((100,133),(0.25,0.325)),((133,167),(0.325,0.475)),((167,200),(0.475,0.575)),((200,233),(0.575,0.665)),((233,267),(0.666,0.75))]
#		rs = self.get_quality()
#		rsper = 100*(float(rs)/self.r0)
#		for a in conversions:
#			if a[0][0]<=rsper<a[0][1]:
#				mid,hi = rsper-a[0][0],a[0][1]-a[0][0]
#				sf = float(mid)/hi
#				ppm = sf * (a[1][1]-a[1][0]) + a[1][0]
#				return ppm
#		return rsper * 0.002808988764

#	def get_CO(self):
#		conversions = [((110,90),(0,1.5)),((90,85),(1.5,5)),((85,80),(5,6)),((80,75),(6,7)),((75,70),(7,8)),((70,65),(8,12)),((65,60),(12,14)),((60,55),(14,18)),((55,50),(18,22))]
#		rs = self.get_quality()
#                rsper = 100*(float(rs)/self.r0)
#                for a in conversions:
#                        if a[0][0]>=rsper>a[0][1]:
#                                mid,hi = rsper-a[0][0],a[0][1]-a[0][0]
#                                sf = float(mid)/hi
#                                ppm = sf * (a[1][1]-a[1][0]) + a[1][0]
#                                return ppm
#                if rsper>110:
#			return 0
#		else:
#			return (1/float(rsper))*1100


if __name__ == "__main__":

    station = AirPi(mode='simulator',loop_interval=2.0)
    for packet in station.genLoopPackets():
        print weeutil.weeutil.timestamp_to_string(packet['dateTime']), packet
        

