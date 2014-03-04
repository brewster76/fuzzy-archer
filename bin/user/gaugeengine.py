#
# Copyright (c) 2013 Nick Dajda <nick.dajda@gmail.com>
#
# Distributed under the terms of the GNU GENERAL PUBLIC LICENSE
#
"""Nick's custom generator for creating visual gauge image files from weewx.

Tested on weewx release 2.5.1
Tested with sqlite, may not work with other databases.

Directions for use:

1) Put this file in the weewx/bin/user directory.
2) Add user.gaugeengine.GaugeGenerator to the list of Generators in skin.conf.
3) Add a [GaugeGenerator] section to skin.conf.
   Any gauges contained in this section are created when the report generator
   runs.
4) Guage names must match the Weewx field name, e.g. outTemp or barometer
5) Here is an example [GaugeGenerator] section:

###############################################################################
#
# Settings for Nick's gauge generator
#
[GaugeGenerator]
    image_width = 180
    image_height = 180
    GAUGE_ROOT = public_html/
    font_path = /usr/share/fonts/truetype/freefont/FreeSans.ttf

    # Colors...
    #
    # Format is 0xBBGGRR, so a pinky-purple color (r=FF, g=00, B=99) which
    # would have an HTML tag of #FF0099 is expressed as 0x9900FF
    fill_color = 0x4242b4
    background_color = 0xffffff
    label_color = 0x000000
    dial_color = 0x707070
    needle_color = 0xb48242
    text_color = 0xb48242

    [[Temperature]]
    minvalue = -20
    maxvalue = 40
    majorstep = 10
    minorstep = 1
    labelfontsize = 15
    digitfontsize = 18	#repeat for other gauges if required
    digittextvpos = 40	#repeat for other gauges if required
    solidneedle = 1     #set = 0 if only outline required
    history = 24
    bins = 120

    [[Pressure]]
    minvalue = 970
    maxvalue = 1050
    majorstep = 20
    minorstep = 10
    labelfontsize = 12

    [[Humidity]]
    minvalue = 0
    maxvalue = 100
    majorstep = 20
    minorstep = 10
    labelfontsize = 13

    [[WindSpeed]]
    minvalue = 0
    maxvalue = 40
    majorstep = 10
    minorstep = 2
    labelfontsize = 15

    [[WindGust]]
    minvalue = 0
    maxvalue = 40
    majorstep = 10
    minorstep = 2
    labelfontsize = 15

    [[WindDirection]]
    labelfontsize = 12

    # By default, needle points towards direction of wind source. Use invert to
    # point towards wind destination. Can be True or False.
    invert = False

    # Number of groups that wind direction history is split into.
    bins = 32

    # hours of data to use for windgauge background shading.
    history = 12
"""

import time
import syslog
import math

import Image
import ImageDraw
import ImageFont

import os.path

import weeutil.weeutil
import weewx.archive
import weewx.reportengine
import weeplot.utilities

from weewx.units import ValueTupleDict, Converter


class GaugeGenerator(weewx.reportengine.CachedReportGenerator):

    """Class for creating nice gauge graphics."""

    def __init__(self, config_dict, skin_dict, gen_ts, first_run, stn_info):
        super(GaugeGenerator, self).__init__(config_dict, skin_dict, gen_ts,
                                             first_run, stn_info)

        self.gauge_dict = self.skin_dict['GaugeGenerator']
        self.units_dict = self.skin_dict['Units']

        self.wheretosaveit = os.path.join(self.config_dict['WEEWX_ROOT'],
                                          self.gauge_dict.get('GAUGE_ROOT', "public_html/"))
        self.Converter = Converter(self.skin_dict['Units']['Groups'])

        self.fillColor = weeplot.utilities.tobgr(self.gauge_dict.get('fill_color', '0x999999'))
        self.fillColorTuple = int2rgb(self.fillColor)

        self.backColor = weeplot.utilities.tobgr(self.gauge_dict.get('background_color', '0xffffff'))
        self.backColorTuple = int2rgb(self.backColor)

        self.labelColor = weeplot.utilities.tobgr(self.gauge_dict.get('label_color', '0x000000'))
        self.dialColor = weeplot.utilities.tobgr(self.gauge_dict.get('dial_color', '0x707070'))
        self.needleColor = weeplot.utilities.tobgr(self.gauge_dict.get('needle_color', '0xb48242'))
        self.textColor = weeplot.utilities.tobgr(self.gauge_dict.get('text_color', '0xb48242'))

        self.fontPath = self.gauge_dict.get('font_path', '/usr/share/fonts/truetype/freefont/FreeSans.ttf')

    def _hexToTuple(self, x):
        b = (x >> 16) & 0xff
        g = (x >> 8) & 0xff
        r = x & 0xff
        return r, g, b

    def _calcColor(self, value, index):
        diff = self.fillColorTuple[index] - self.backColorTuple[index]
        newColor = self.backColorTuple[index] + int(diff * value)

        if newColor < 0:
            newColor = 0

        if newColor > 0xff:
            newColor = 0xff

        return newColor

    def run(self):
        t1 = time.time()
        gaugesDrawn = 0

        syslog.syslog(syslog.LOG_DEBUG,
                      "GaugeGenerator: Gauge generator code run... marvellous.")

        # Load up config info from skin.conf file
        archivedb = self._getArchive(self.skin_dict['archive_database'])

        rec = self.getRecord(archivedb, archivedb.lastGoodStamp())
        record_dict_vtd = weewx.units.ValueTupleDict(rec)


        for gauge in self.gauge_dict:
            # Only interested in the section headings within the gauge config file
            if isinstance(self.gauge_dict[gauge], dict):

                # Do we have a reading for it?

                try:
                    unitType = self.units_dict['Groups'][record_dict_vtd[gauge][2]]
                except:
                    syslog.syslog(syslog.LOG_INFO, "GaugeGenerator: Could not find reading for gauge '%s'" % gauge)
                    return

                # Convert it to units in skin.conf file
                valueTuple = weewx.units.convert(record_dict_vtd[gauge], unitType)

                syslog.syslog(syslog.LOG_DEBUG, "GaugeGenerator: %s = %s" % (gauge, valueTuple[0]))

                if gauge == 'windDir':
                    self.drawwindgauge(gauge)
                else:
                    self.drawGauge(gauge, valueTuple, unitType)

                gaugesDrawn += 1

        t2 = time.time()
        syslog.syslog(
            syslog.LOG_INFO, "GaugeGenerator: Created %d gauges in %.2f seconds." %
            (gaugesDrawn, t2 - t1))

    def drawwindgauge(self, gaugename):
        """Wind direction gauge generator with shaded background to indicate historic wind directions"""

        imagewidth = int(self.gauge_dict.get('image_width', 180))
        imageheight = int(self.gauge_dict.get('image_height', 180))

        #
        # --- New and untested code:
        #
        imagewidth = int(self.gauge_dict[gaugename].get('image_width', imagewidth))
        imageheight = int(self.gauge_dict[gaugename].get('image_height', imageheight))
        #
        # ---

        imageorigin = (imagewidth / 2, imageheight / 2)

        syslog.syslog(syslog.LOG_DEBUG,
                      "GaugeGenerator: Generating %s gauge, (%d x %d)" % (gaugename, imagewidth, imageheight))

        labelFontSize = int(self.gauge_dict[gaugename].get('labelfontsize', 12))
        digitFontSize = int(self.gauge_dict[gaugename].get('digitfontsize', 20))
        digitTextVPos = float(self.gauge_dict[gaugename].get('digittextvpos', 40)) / 100
        solidNeedle = float(self.gauge_dict[gaugename].get('solidneedle', 0))

        invertGauge = weeutil.weeutil.tobool(self.gauge_dict[gaugename].get('invert', False))

        archivedb = self._getArchive(self.skin_dict['archive_database'])

        (data_time, data_value) = archivedb.getSqlVectors('windDir', archivedb.lastGoodStamp() -
                                                          self.gauge_dict[gaugename].as_int('history') * 60 * 60,
                                                          archivedb.lastGoodStamp())

        for rec in data_value:
            syslog.syslog(syslog.LOG_DEBUG, "GaugeGenerator: %s" % rec)

        # Number of bins to count wind history into
        numBins = int(self.gauge_dict[gaugename].get('bins', 16))

        # One data point recorded every 5 mins for 'history' number of hours
        numPoints = int(self.gauge_dict[gaugename].get('history'), 12) * 60 / 5

        #
        # Get the wind data
        #
        buckets = [0.0] * numBins

        #
        # Now looks up historic data using weewx helper functions... Thanks Tom!
        #
        archive_db = self.config_dict['StdArchive']['archive_database']
        archive = weewx.archive.Archive.open(
            self.config_dict['Databases'][archive_db])

        windDirNow = None
        windSpeedNow = None

        #
        # TODO: Get rid of this SQL stuff and collect the data using weewx helper functions
        #       (like the histogram function does)
        #
        for row in archive.genSql("SELECT windDir, windSpeed FROM archive ORDER BY dateTime DESC LIMIT %d" % numPoints):
            if row[0] is not None:
                try:
                    windDir = float(row[0])
                except:
                    syslog.syslog(
                        syslog.LOG_INFO, "drawWindGauge: Cannot convert wind direction into a float value")
                else:

                    if (windDir < 0) or (windDir > 360):
                        syslog.syslog(
                            syslog.LOG_INFO, "drawWindGauge: %f should be in the range 0-360 degrees",
                            windDir)
                    else:
                        buckets[int(windDir * numBins / 360)] += 1

                        if windDirNow is None:
                            windDirNow = windDir

            if windSpeedNow is None:
                if row[1] is not None:
                    try:
                        windSpeedNow = float(row[1])
                    except:
                        syslog.syslog(
                            syslog.LOG_INFO, "drawWindGauge; Cannot convert wind speed into a float")

        # If we haven't been able to find a windSpeed then there must be no
        # wind...
        if windSpeedNow is not None:
            maxval = maxvalue(buckets)
            buckets = [i / maxval for i in buckets]

        #
        # Draw the gauge
        #
        im = Image.new("RGB", (imagewidth, imageheight), (255, 255, 255))

        draw = ImageDraw.Draw(im)

        if imagewidth < imageheight:
            radius = imagewidth * 0.45
        else:
            radius = imageheight * 0.45

        sansFont = ImageFont.truetype(self.fontPath, labelFontSize)
        bigSansFont = ImageFont.truetype(self.fontPath, digitFontSize)

        # Plot shaded pie slices if there is sufficient data
        if windSpeedNow is not None:
            angleStep = 360.0 / numBins
            angle = 0.0

            if not invertGauge:
                angle = 180.0

            for i in range(0, numBins, 1):
                fillColor = (self._calcColor(buckets[i], 0), self._calcColor(
                    buckets[i], 1), self._calcColor(buckets[i], 2))

                draw.pieslice(
                    (int(imageorigin[
                        0] - radius), int(
                        imageorigin[1] - radius), int(
                        imageorigin[0] + radius),
                     int(imageorigin[1] + radius)), int(angle + 90), int(angle + angleStep + 90), fill=fillColor)
                angle += angleStep

        # Compass points
        labels = ['N', 'E', 'S', 'W']
        if digitTextVPos > 0.5:
             labels = ['N', 'E', ' ', 'W']

        for i in range(0, 4, 1):
            angle = i * math.radians(90) + math.radians(180)

            # Major tic
            startPoint = (imageorigin[0] - radius * math.sin(angle)
                          * 0.93, imageorigin[1] + radius * math.cos(angle) * 0.93)
            endPoint = (imageorigin[0] - radius * math.sin(angle),
                        imageorigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=self.dialColor)

            labelText = labels[i]
            stringSize = sansFont.getsize(labelText)

            labelPoint = (imageorigin[0] - radius * math.sin(angle)
                          * 0.80, imageorigin[1] + radius * math.cos(angle) * 0.80)
            labelPoint = (labelPoint[0] - stringSize[0]
                          / 2, labelPoint[1] - stringSize[1] / 2)

            draw.text(labelPoint, labelText,
                      font=sansFont, fill=self.labelColor)

            # Minor tic
            angle += math.radians(45)
            startPoint = (imageorigin[0] - radius * math.sin(angle)
                          * 0.93, imageorigin[1] + radius * math.cos(angle) * 0.93)
            endPoint = (imageorigin[0] - radius * math.sin(angle),
                        imageorigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=self.dialColor)

        # The needle
        if windSpeedNow is not None:
            if invertGauge:
                angle = math.radians(windDirNow)
            else:
                angle = math.radians(windDirNow + 180)

            # As designed orignally, this draws the needle pointing towards
            # wind destination, not source (i.e. inverted)
            endPoint = (imageorigin[0] - radius * math.sin(angle)
                        * 0.7, imageorigin[1] + radius * math.cos(angle) * 0.7)
            leftPoint = (
                imageorigin[0] - radius *
                math.sin(angle - math.pi * 7 / 8) * 0.2,
                imageorigin[1] + radius * math.cos(angle - math.pi * 7 / 8) * 0.2)
            rightPoint = (
                imageorigin[0] - radius *
                math.sin(angle + math.pi * 7 / 8) * 0.2,
                imageorigin[1] + radius * math.cos(angle + math.pi * 7 / 8) * 0.2)
            midPoint = (
                imageorigin[0] - radius * math.sin(angle + math.pi) * 0.1,
                imageorigin[1] + radius * math.cos(angle + math.pi) * 0.1)

            if solidNeedle == 1:
                draw.polygon((midPoint, leftPoint, endPoint, rightPoint), fill=self.needleColor, outline=self.needleColor)
            else:
                draw.line((leftPoint, endPoint), fill=self.needleColor)
                draw.line((rightPoint, endPoint), fill=self.needleColor)
                draw.line((leftPoint, midPoint), fill=self.needleColor)
                draw.line((rightPoint, midPoint), fill=self.needleColor)

        # Outline
        draw.ellipse(((imageorigin[0] - radius, imageorigin[1] - radius),
                      (imageorigin[0] + radius, imageorigin[1] + radius)), outline=self.dialColor)

        # Digital value text
        degreeSign = u'\N{DEGREE SIGN}'

        if windSpeedNow is not None:
            digitalText = "%d" % windDirNow + degreeSign
        else:
            digitalText = "No wind"

        stringSize = bigSansFont.getsize(digitalText)
        draw.text(
            (imageorigin[0] - stringSize[0] / 2, imageorigin[1]
             + radius * digitTextVPos - stringSize[1] / 2), digitalText,
            font=bigSansFont, fill=self.textColor)

        del draw

        im.save(self.wheretosaveit + gaugename + "Gauge.png", "PNG")

    def histogram(self, gaugeName, fieldName, unitType, numBins):
        minVal = self.gauge_dict[gaugeName].as_float('minvalue')
        maxval = self.gauge_dict[gaugeName].as_float('maxvalue')

        buckets = [0.0] * numBins
        bucketSpan = (maxval - minVal) / numBins
        numPoints = 0
        roof = 0

        archivedb = self._getArchive(self.skin_dict['archive_database'])

        (data_time, data_value) = archivedb.getSqlVectors(gaugeName, archivedb.lastGoodStamp() -
                                                          int(self.gauge_dict[gaugeName].get('history', 12)) * 60 * 60,
                                                          archivedb.lastGoodStamp())
        for t1 in data_time:
            for t2 in t1:
                rec = archivedb.getRecord(t2)

                if rec is not None:

                    record_dict_vtd = weewx.units.ValueTupleDict(rec)
                    valueTuple = weewx.units.convert(record_dict_vtd[gaugeName], unitType)

                    try:
                        histValue = float(valueTuple[0])
                    except:
                        syslog.syslog(syslog.LOG_DEBUG, "GaugeGenerator->histogram(): Cannot decode reading for gauge '%s'"
                                     % gaugeName)
                    else:
                        if histValue > maxval:
                            syslog.syslog(syslog.LOG_DEBUG,
                                          "histogram: %s = %f is higher than maxvalue (%f)" % (fieldName, histValue, maxval))
                        elif histValue < minVal:
                            syslog.syslog(syslog.LOG_DEBUG,
                                          "histogram: %s = %f is lower than minvalue (%f)" % (fieldName, histValue, minVal))
                        else:
                            bucketNum = int((histValue - minVal) / bucketSpan)

                            if bucketNum >= numBins:
                                syslog.syslog(syslog.LOG_INFO, "histogram: value %f gives bucket higher than numBins (%d)"
                                              % (histValue, numBins))
                            else:
                                buckets[bucketNum] += 1.0
                                numPoints += 1

                                if buckets[bucketNum] > roof:
                                    roof = buckets[bucketNum]

        buckets = [i / roof for i in buckets]

        return buckets

    def drawGauge(self, gaugeName, valueTuple, unitType):
        imageWidth = int(self.gauge_dict.get('image_width', 180))
        imageHeight = int(self.gauge_dict.get('image_height', 180))

        #
        # --- New and untested code:
        #
        imagewidth = int(self.gauge_dict[gaugename].get('image_width', imagewidth))
        imageheight = int(self.gauge_dict[gaugename].get('image_height', imageheight))
        #
        # ---

        imageOrigin = (imageWidth / 2, imageHeight / 2)

        # Check gauge value is usable
        if valueTuple is None:
            syslog.syslog(syslog.LOG_DEBUG, "GaugeGenerator: Generating %s gauge, (%d x %d), valueTuple = None" % (
                gaugeName, imageWidth, imageHeight))
            digitalText = "N/A"
            digitalUnitsText = ""
        else:
#            digitalText = self.units_dict['StringFormats'][valueTuple[1]] % valueTuple[0] + \
#                          self.units_dict['Labels'][valueTuple[1]]
            digitalText = self.units_dict['StringFormats'][valueTuple[1]] % valueTuple[0]
            digitalUnitsText = self.units_dict['Labels'][valueTuple[1]]

            syslog.syslog(syslog.LOG_DEBUG, "GaugeGenerator: Generating %s gauge, (%d x %d), value = %s %s" % (
                gaugeName, imageWidth, imageHeight, digitalText, digitalUnitsText))

        minVal = self.gauge_dict[gaugeName].as_float('minvalue')
        maxval = self.gauge_dict[gaugeName].as_float('maxvalue')
        majorStep = float(self.gauge_dict[gaugeName].get('majorstep', 10))
        minorStep = float(self.gauge_dict[gaugeName].get('minorstep', 1))
        labelFontSize = int(self.gauge_dict[gaugeName].get('labelfontsize', 12))
        digitFontSize = int(self.gauge_dict[gaugeName].get('digitfontsize', 20))
        digitTextVPos = float(self.gauge_dict[gaugeName].get('digittextvpos', 40)) / 100
        solidNeedle = float (self.gauge_dict[gaugeName].get('solidneedle', 0))

        labelFormat = "%d"

        minAngle = 45  # in degrees
        maxAngle = 315

        im = Image.new("RGB", (imageWidth, imageHeight), (255, 255, 255))

        draw = ImageDraw.Draw(im)

        if imageWidth < imageHeight:
            radius = imageWidth * 0.45
        else:
            radius = imageHeight * 0.45

        # Background

        if int(self.gauge_dict[gaugeName].get('history', 0)) > 0:

            numBins = int(self.gauge_dict[gaugeName].get('bins', 100))
            buckets = self.histogram(gaugeName, gaugeName, unitType, numBins)

            angle = float(minAngle)
            angleStep = (maxAngle - minAngle) / float(numBins)
            for i in range(0, numBins, 1):
                fillColor = (self._calcColor(buckets[i], 0), self._calcColor(
                    buckets[i], 1), self._calcColor(buckets[i], 2))

                draw.pieslice(
                    (int(imageOrigin[
                        0] - radius), int(
                        imageOrigin[1] - radius), int(
                        imageOrigin[0] + radius),
                     int(imageOrigin[1] + radius)), int(angle + 90), int(angle + angleStep + 90), fill=fillColor)
                angle += angleStep

        draw.ellipse(((imageOrigin[0] - radius, imageOrigin[1] - radius),
                      (imageOrigin[0] + radius, imageOrigin[1] + radius)), outline=self.dialColor)

        sansFont = ImageFont.truetype(self.fontPath, labelFontSize)
        bigSansFont = ImageFont.truetype(self.fontPath, digitFontSize)

        labelValue = minVal

        # Major tic marks and scale labels
        for angle in frange(math.radians(minAngle), math.radians(maxAngle), int(1 + (maxval - minVal) / majorStep)):
            startPoint = (imageOrigin[0] - radius * math.sin(angle)
                          * 0.93, imageOrigin[1] + radius * math.cos(angle) * 0.93)
            endPoint = (imageOrigin[0] - radius * math.sin(angle),
                        imageOrigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=self.dialColor)

            labelText = str(labelFormat % labelValue)
            stringSize = sansFont.getsize(labelText)

            labelPoint = (
                imageOrigin[0] - radius * math.sin(angle) * 0.80, imageOrigin[1] + radius * math.cos(angle) * 0.80)
            labelPoint = (labelPoint[0] - stringSize[0]
                          / 2, labelPoint[1] - stringSize[1] / 2)

            draw.text(labelPoint, labelText,
                      font=sansFont, fill=self.labelColor)
            # draw.point(labelPoint)
            labelValue += majorStep

        # Minor tic marks
        for angle in frange(math.radians(minAngle), math.radians(maxAngle), int(1 + (maxval - minVal) / minorStep)):
            startPoint = (imageOrigin[0] - radius * math.sin(angle)
                          * 0.97, imageOrigin[1] + radius * math.cos(angle) * 0.97)
            endPoint = (imageOrigin[0] - radius * math.sin(angle),
                        imageOrigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=self.dialColor)

        # The needle
        if valueTuple[0] is not None:
            angle = math.radians(minAngle + (valueTuple[0] - minVal)
                                 * (maxAngle - minAngle) / (maxval - minVal))
            endPoint = (
                imageOrigin[0] - radius * math.sin(angle) * 0.7, imageOrigin[1] + radius * math.cos(angle) * 0.7)
            leftPoint = (
                imageOrigin[0] - radius *
                math.sin(angle - math.pi * 7 / 8) * 0.2,
                imageOrigin[1] + radius * math.cos(angle - math.pi * 7 / 8) * 0.2)
            rightPoint = (
                imageOrigin[0] - radius *
                math.sin(angle + math.pi * 7 / 8) * 0.2,
                imageOrigin[1] + radius * math.cos(angle + math.pi * 7 / 8) * 0.2)
            midPoint = (
                imageOrigin[0] - radius * math.sin(angle + math.pi) * 0.1,
                imageOrigin[1] + radius * math.cos(angle + math.pi) * 0.1)

            if solidNeedle == 1:
                draw.polygon((midPoint, leftPoint, endPoint, rightPoint), fill=self.needleColor, outline=self.needleColor)
            else:
                draw.line((leftPoint, endPoint), fill=self.needleColor)
                draw.line((rightPoint, endPoint), fill=self.needleColor)
                draw.line((leftPoint, midPoint), fill=self.needleColor)
                draw.line((rightPoint, midPoint), fill=self.needleColor)

        # Digital value text
        digitalUnitsText = unicode(digitalUnitsText, 'utf8')
        stringSize = bigSansFont.getsize(digitalUnitsText)
        draw.text((imageOrigin[0] - stringSize[0] / 2, imageOrigin[1]+ radius * (digitTextVPos * 0.66) - stringSize[1] / 2), digitalUnitsText,
            font=bigSansFont, fill=self.textColor)

        digitalText = unicode(digitalText, 'utf8')
        stringSize = bigSansFont.getsize(digitalText)
        draw.text((imageOrigin[0] - stringSize[0] / 2, imageOrigin[1]+ radius * digitTextVPos - stringSize[1] / 2), digitalText,
            font=bigSansFont, fill=self.textColor)

        del draw

        im.save(self.wheretosaveit + gaugeName + "Gauge.png", "PNG")

    def getRecord(self, archivedb, time_ts):
        # Return a value tuple dictionary which can be used to get current
        # readings in skin units
        record_dict = archivedb.getRecord(time_ts)

        return ValueTupleDict(record_dict)


def int2rgb(x):
#
# Stolen from genploy.py Weewx file
#
    b = (x >> 16) & 0xff
    g = (x >> 8) & 0xff
    r = x & 0xff
    return r, g, b


def frange(start, stop, n):
    L = [0.0] * n
    nm1 = n - 1
    nm1inv = 1.0 / nm1
    for i in range(n):
        L[i] = nm1inv * (start * (nm1 - i) + stop * i)
    return L


def maxvalue(array):
    maxval = 0.0

    for i in array:
        if i > maxval:
            maxval = i

    return maxval
