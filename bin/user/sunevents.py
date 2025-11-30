# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
#    Author: Michael Kainzbauer (github: mkainzbauer)
"""calculates events (before sunrise, before sunset, end of twilight, start of twilight for the
 given timespan and angle

############################################################################################
#
"""

from math import pi

import logging
from datetime import datetime
from datetime import timezone

log = logging.getLogger(__name__)

try:
    from skyfield import api, almanac
except ImportError:
    api = None


class SunEvents():
    def __init__(self, start_ts, end_ts, lon, lat, elev):
        if api is None:
            log.info("skyfield not found, some features, like day/night background colors for charts are not available.")
            return
        # Load ephemeris data
        self.ts = api.load.timescale()
        self.eph = api.load('de440s.bsp')
        self.start_ts = int(start_ts)
        self.end_ts = int(end_ts)
        self.sun = self.eph['sun']
        self.topos = api.wgs84.latlon(float(lat), float(lon), elev)
        self.observer = self.eph['earth'] + self.topos
        self.transits = []

    def append_transits(self, values):
        for value in values:
            value_ts = value[0]
            value_angle = value[1]
            value_text = value[2]
            if value_ts is not None and self.start_ts <= value_ts <= self.end_ts:
                self.transits.append([value_ts, value_angle, value_text])

    def get_transits(self, angle):
        sf_start_time = self._ts_to_skyfield_time(self.start_ts)
        sf_end_time = self._ts_to_skyfield_time(self.end_ts)
        self.append_transits([[self.start_ts, self.sun_alt_degrees(sf_start_time), "start"]])

        lower_rise_times, y = almanac.find_risings(self.observer, self.sun, sf_start_time, sf_end_time, -angle)
        for t in lower_rise_times:
            self.append_transits([[self._skyfield_time_to_ts(t), -angle, "rising"]])

        upper_rise_times, y = almanac.find_risings(self.observer, self.sun, sf_start_time, sf_end_time, angle)
        for t in upper_rise_times:
            self.append_transits([[self._skyfield_time_to_ts(t), angle, "rising"]])
        
        lower_set_times, y = almanac.find_settings(self.observer, self.sun, sf_start_time, sf_end_time, angle)
        for t in lower_set_times:
            self.append_transits([[self._skyfield_time_to_ts(t), angle, "setting"]])

        upper_set_times, y = almanac.find_settings(self.observer, self.sun, sf_start_time, sf_end_time, -angle)
        for t in upper_set_times:
            self.append_transits([[self._skyfield_time_to_ts(t), -angle, "setting"]])

        f = almanac.meridian_transits(self.eph, self.sun, self.topos)
        transits, y = almanac.find_discrete(sf_start_time, sf_end_time, f)
        i = 0
        for t in transits:
            transit_type = "transit" if int(y[i]) == 1 else "antitransit"
            i += 1
            self.append_transits([[self._skyfield_time_to_ts(t), self.sun_alt_degrees(t), transit_type]])

        self.append_transits([[self.end_ts, self.sun_alt_degrees(sf_end_time), "end"]])

        self.transits.sort(key=lambda x: x[0])
        return self.transits
    
    def _ts_to_skyfield_time(self, unix_timestamp: int):
        """Convert Unix timestamp to Skyfield time object."""
        dt = datetime.fromtimestamp(int(unix_timestamp), tz=timezone.utc)
        return self.ts.utc(dt)
    
    def _skyfield_time_to_ts(self, sky_time) -> int:
        """Convert Skyfield time object to Unix timestamp."""
        dt = sky_time.utc_datetime()
        return int(dt.timestamp())
    
    def sun_alt_degrees(self, time):
        alt, _, _ = self.observer.at(time).observe(self.sun).apparent().altaz()
        return int(alt.degrees)

