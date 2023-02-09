# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
#    Author: Michael Kainzbauer (github: mkainzbauer)
"""calculates events (before sunrise, before sunset, end of twilight, start of twilight for the
 given timespan and angle

Tested on Weewx release 4.10.1

############################################################################################
#
"""

from math import pi

import logging
from weeutil.weeutil import startOfDayUTC
from weewx.almanac import djd_to_timestamp, timestamp_to_djd

log = logging.getLogger(__name__)

try:
    import ephem
except ImportError:
    log.info("pyephem not found, some features are not available.")

def rad_2_deg(value):
    return value * 180.0 / pi


def deg_2_rad(value):
    return value * pi / 180.0


class SunEvents():
    def __init__(self, start_ts, end_ts, lon, lat, elev):
        self.start_ts = start_ts
        self.end_ts = end_ts
        station = ephem.Observer()
        station.lon, station.lat, station.elevation = lon, lat, elev
        self.station = station
        self.transits = []

    def calc_rise_set(self, horizon, use_center=True):
        self.station.horizon = horizon
        try:
            rise_ts = int(
                djd_to_timestamp(self.station.next_rising(ephem.Sun(), use_center=use_center)))
        except ephem.CircumpolarError as e:
            rise_ts = None
            log.debug(e.args[0])
        try:
            set_ts = int(
                djd_to_timestamp(self.station.next_setting(ephem.Sun(), use_center=use_center)))
        except ephem.CircumpolarError as e:
            set_ts = None
            log.debug(e.args[0])

        return (rise_ts, horizon, "rising"), (set_ts, horizon, "setting")

    def calc_transits(self):
        transit_date = self.station.next_transit(ephem.Sun())
        transit_date_ts = int(djd_to_timestamp(transit_date))
        antitransit_date = self.station.next_antitransit(ephem.Sun())
        antitransit_date_ts = int(djd_to_timestamp(antitransit_date))

        station_date = self.station.date

        self.station.date = transit_date
        sun = ephem.Sun(self.station)
        transit_alt = sun.alt

        self.station.date = antitransit_date
        sun = ephem.Sun(self.station)
        antitransit_alt = sun.alt

        self.station.date = station_date

        return (transit_date_ts, transit_alt, "transit"), (
        antitransit_date_ts, antitransit_alt, "antitransit")

    def append_transits(self, values):
        for value in values:
            value_ts = value[0]
            value_angle = value[1]
            value_text = value[2]
            if value_ts is not None and self.start_ts <= value_ts <= self.end_ts:
                self.transits.append([value_ts, rad_2_deg(value_angle), value_text])

    def get_transits(self, angle_degree):

        angle_rad = deg_2_rad(angle_degree)
        ephem_start = ephem.Date(timestamp_to_djd(self.start_ts))
        self.station.date = ephem_start
        sun = ephem.Sun(self.station)
        self.append_transits([[self.start_ts, sun.alt, "start"]])

        for t in range(self.start_ts - 3600 * 24, self.end_ts + 3600 * 24 + 1, 3600 * 24):
            start_of_day_utc = startOfDayUTC(t)

            self.station.date = ephem.Date(timestamp_to_djd(start_of_day_utc))

            lower_rise_set = self.calc_rise_set(-angle_rad)
            self.append_transits(lower_rise_set)
            upper_rise_set = self.calc_rise_set(angle_rad)
            self.append_transits(upper_rise_set)

            transit_antitransit = self.calc_transits()
            self.append_transits(transit_antitransit)

        ephem_end = timestamp_to_djd(self.end_ts)
        self.station.date = ephem_end
        sun = ephem.Sun(self.station)
        self.append_transits([[self.end_ts, sun.alt, "end"]])

        self.transits.sort(key=lambda x: x[0])
        return self.transits

