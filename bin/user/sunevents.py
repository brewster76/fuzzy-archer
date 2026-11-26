# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
#    Author: Michael Kainzbauer (github: mkainzbauer)
"""calculates events (before sunrise, before sunset, end of twilight, start of twilight for the
 given timespan and angle

############################################################################################
#
"""

import logging
import math
import os
from datetime import datetime
from datetime import timezone

log = logging.getLogger(__name__)

try:
    from skyfield import api, almanac
except ImportError:
    api = None


class SunEvents():
    def __init__(self, start_ts, end_ts, lon, lat, elev, path, ephemeris):
        if api is None:
            return
        # Load ephemeris data
        load = api.Loader(path)
        self.eph = load(ephemeris)

        self.ts = load.timescale()
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


def sun_position(ts, lon, lat):
    """(altitude in degrees, hour angle in degrees -180..180) of the sun's center, without refraction.

    Low-precision formula of the Astronomical Almanac (about 0.01° for 1950-2050), no dependencies.
    """
    n = ts / 86400.0 - 10957.5  # days since J2000.0
    mean_longitude = math.radians((280.460 + 0.9856474 * n) % 360)
    mean_anomaly = math.radians((357.528 + 0.9856003 * n) % 360)
    ecliptic_longitude = mean_longitude + math.radians(1.915) * math.sin(mean_anomaly) \
        + math.radians(0.020) * math.sin(2 * mean_anomaly)
    obliquity = math.radians(23.439 - 0.0000004 * n)
    right_ascension = math.atan2(math.cos(obliquity) * math.sin(ecliptic_longitude), math.cos(ecliptic_longitude))
    declination = math.asin(math.sin(obliquity) * math.sin(ecliptic_longitude))
    sidereal = math.radians((280.46061837 + 360.98564736629 * n + lon) % 360)
    hour_angle = math.atan2(math.sin(sidereal - right_ascension), math.cos(sidereal - right_ascension))
    phi = math.radians(lat)
    sin_alt = math.sin(phi) * math.sin(declination) + math.cos(phi) * math.cos(declination) * math.cos(hour_angle)
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_alt)))), math.degrees(hour_angle)


class ApproxSunEvents(object):
    """Same events as SunEvents.get_transits, computed without skyfield (approximation).

    Crossings are searched on a STEP grid and refined by bisection to one second; altitude
    crossings that start and end within one step (grazing sun near the poles) may be missed.
    """
    STEP = 300

    def __init__(self, start_ts, end_ts, lon, lat):
        self.start_ts = int(start_ts)
        self.end_ts = int(end_ts)
        self.lon = float(lon)
        self.lat = float(lat)

    def _altitude(self, ts):
        return sun_position(ts, self.lon, self.lat)[0]

    def _sin_hour_angle(self, ts):
        return math.sin(math.radians(sun_position(ts, self.lon, self.lat)[1]))

    def _grid(self):
        times = list(range(self.start_ts, self.end_ts, self.STEP))
        times.append(self.end_ts)
        return times

    @staticmethod
    def _bisect(f, a, b):
        fa = f(a)
        while b - a > 1:
            m = (a + b) // 2
            fm = f(m)
            if (fm < 0) == (fa < 0):
                a, fa = m, fm
            else:
                b = m
        return b

    def _crossings(self, f, times):
        """[(ts, rising)] for every sign change of f between neighbouring grid times."""
        result = []
        values = [f(t) for t in times]
        for i in range(1, len(times)):
            before, after = values[i - 1], values[i]
            if (before < 0) != (after < 0):
                result.append((self._bisect(f, times[i - 1], times[i]), after >= 0))
        return result

    def get_transits(self, angle):
        times = self._grid()
        events = [[self.start_ts, int(self._altitude(self.start_ts)), "start"]]
        for target in sorted({-angle, angle}):
            for ts, rising in self._crossings(lambda t: self._altitude(t) - target, times):
                events.append([ts, target, "rising" if rising else "setting"])
        for ts, increasing in self._crossings(self._sin_hour_angle, times):
            # sin(hour angle) rises through 0 at the upper culmination, falls through 0 at the lower one
            events.append([ts, int(self._altitude(ts)), "transit" if increasing else "antitransit"])
        events.append([self.end_ts, int(self._altitude(self.end_ts)), "end"])
        events.sort(key=lambda x: x[0])
        return events


_approximation_logged = False


def compute_sun_events(start_ts, end_ts, lon, lat, elev, path, ephemeris, angle):
    """Sun events with skyfield when available, otherwise (or when skyfield fails) approximated."""
    global _approximation_logged
    #if api is not None:
    #    try:
    #        os.makedirs(path, exist_ok=True)
    #        return SunEvents(start_ts, end_ts, lon, lat, elev, path, ephemeris).get_transits(angle)
    #    except Exception as e:
    #        log.warning("skyfield sun events failed, using approximation: %s: %s", type(e).__name__, e)
    #elif not _approximation_logged:
    #    log.info("skyfield not found: day/night backgrounds use an approximated sun position")
    #    _approximation_logged = True
    return ApproxSunEvents(start_ts, end_ts, lon, lat).get_transits(angle)

