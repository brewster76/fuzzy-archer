#
# Copyright (c) 2013 Nick Dajda <nick.dajda@gmail.com>
#
# Distributed under the terms of the GNU GENERAL PUBLIC LICENSE
#
"""Nick's custom generator for creating visual gauge image files from weewx.

Tested on weewx release 2.4.0

Directions for use:

1) Put this file in the weewx/bin/user directory.
2) Add user.nicksengines.GaugeGenerator to the list of Generators in skin.conf.
3) Add a [GaugeGenerator] section to skin.conf. 
   Any gauges contained in this section are created when the report generator runs.

4) Here is an example [GaugeGenerator] section:

############################################################################################
#
# Settings for Nick's gauge generator
#
[GaugeGenerator]
    image_width = 180
    image_height = 180

    # Save gauges in the default web directory
    GAUGE_ROOT = public_html/

    [[Temperature]]
    minvalue = -20
    maxvalue = 40
    majorstep = 10
    minorstep = 1
    labelfontsize = 15        
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
# Hours of historic data to use for gauge background shading
    history = 3
"""

import time
import syslog
import math
import Image, ImageDraw, ImageFont
import os.path

import weewx.reportengine
import weewx.archive
from weewx.units import Formatter, Converter, dictFromStd, ValueDict

class GaugeGenerator(weewx.reportengine.CachedReportGenerator):
    """Class for creating nice gauge graphics."""

    def __init__(self, config_dict, skin_dict, gen_ts, first_run, stn_info):
        super(GaugeGenerator, self).__init__(config_dict, skin_dict, gen_ts, first_run, stn_info)
        self.formatter = Formatter.fromSkinDict(self.skin_dict)
        self.gauges = [{'field': "outTemp", 'name': "Temperature"},
                       {'field': "barometer", 'name': "Pressure"},
                       {'field': "windSpeed", 'name': "WindSpeed"},
                       {'field': "windGust", 'name': "WindGust"},
                       {'field': "outHumidity", 'name': "Humidity"},
                       {'field': "windDir", 'name': "WindDirection"}]
        self.gauge_dict = self.skin_dict['GaugeGenerator']
        self.converter = Converter.fromSkinDict(self.skin_dict)
        self.wheretosaveit = os.path.join(self.config_dict['WEEWX_ROOT'], self.gauge_dict.get('GAUGE_ROOT'))

    def run(self):
        t1 = time.time()

        syslog.syslog(syslog.LOG_INFO, "reportengine: Gauge generator code run (yippee!)")

        # Load up config info from skin.conf file

        archivedb = self._getArchive(self.skin_dict['archive_database'])

        rec = self.getRecord(archivedb, archivedb.lastGoodStamp())

        if rec is not None:

            # Draw a gauge for everything that has a config entry
            for gauge in self.gauge_dict:
                # Is it actually a gauge?             
                for gaugeinfo in self.gauges:
                    if gaugeinfo['name'] == gauge:
                        if rec.has_key(gaugeinfo['field']):
                            # TODO: Look up units actually used by quantity and call appropriate lookup function
                            if gaugeinfo['field'] == 'outTemp': self.drawGauge(rec[gaugeinfo['field']].degree_C.raw,
                                                                               gaugeinfo['name'])
                            if gaugeinfo['field'] == 'barometer': self.drawGauge(rec[gaugeinfo['field']].mbar.raw,
                                                                                 gaugeinfo['name'])
                            if gaugeinfo['field'] == 'windSpeed': self.drawGauge(
                                rec[gaugeinfo['field']].mile_per_hour.raw, gaugeinfo['name'])
                            if gaugeinfo['field'] == 'windGust': self.drawGauge(
                                rec[gaugeinfo['field']].mile_per_hour.raw, gaugeinfo['name'])

                            if gaugeinfo['field'] == 'outHumidity':
                            # Can we make a string out of this?
                                try:
                                    humidity = float(str(rec[gaugeinfo['field']]).strip('%'))
                                except:
                                    syslog.syslog(syslog.LOG_INFO,
                                                  "reportengine: outHumidity value not usable '%s'" % rec[
                                                      gaugeinfo['field']])
                                else:
                                    syslog.syslog(syslog.LOG_INFO, "reportengine: Humidity = %f" % humidity)
                                    self.drawGauge(humidity, gaugeinfo['name'])

                            if gaugeinfo['field'] == 'windDir': self.drawwindgauge(gaugeinfo['name'])

        t2 = time.time()
        syslog.syslog(syslog.LOG_INFO, "reportengine: Time taken %.2f seconds." % (t2 - t1))


    def drawwindgauge(self, gaugename):
        """Wind direction gauge generator with shaded background to indicate historic wind directions"""

        imagewidth = self.gauge_dict.as_int('image_width')
        imageheight = self.gauge_dict.as_int('image_height')
        imageorigin = (imagewidth / 2, imageheight / 2)

        syslog.syslog(syslog.LOG_INFO,
                      "reportengine: Generating %s gauge, (%d x %d)" % (gaugename, imagewidth, imageheight))

        labelFontSize = self.gauge_dict[gaugename].as_int('labelfontsize')

        archivedb = self._getArchive(self.skin_dict['archive_database'])
        (data_time, data_value) = archivedb.getSqlVectors('windDir',
                                                          archivedb.lastGoodStamp() - self.gauge_dict[gaugename].as_int(
                                                              'history') * 60,
                                                          archivedb.lastGoodStamp(), 300, 'avg')

        for rec in data_value:
            syslog.syslog(syslog.LOG_INFO, "eportengine: %s" % rec)

        # Number of bins to count wind history into
        numBins = 16

        # One data point recorded every 5 mins for 'history' number of hours
        numPoints = self.gauge_dict[gaugename].as_int('history') * 60 / 5

        #
        # Get the wind data
        #
        buckets = [0.0] * numBins

        # 22 July 2013
        # 
        # Now looks up historic data using weewx helper functions... Thanks Tom! 
        #        
        archive_db = self.config_dict['StdArchive']['archive_database']
        archive = weewx.archive.Archive.open(self.config_dict['Databases'][archive_db])

        windDir = None
        windDirNow = None
        windSpeedNow = None

        for row in archive.genSql("SELECT windDir, windSpeed FROM archive ORDER BY dateTime DESC LIMIT %d" % numPoints):
            # This line is occasionally crashing out with error: 
            # TypeError: float() argument must be a string or a number
            if row[0] is not None:
                windDir = float(row[0])
                if (windDir < 0) or (windDir > 360):
                    syslog.syslog(syslog.LOG_INFO, "drawFunkyWindGauge: %f should be in the range 0-360 degrees",
                                  windDir)
                else:
                    buckets[int(windDir * numBins / 360)] += 1

            if windSpeedNow is None:
                windSpeedNow = float(row[1])

            if windDirNow is None:
                windDirNow = windDir

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

        sansFont = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", labelFontSize)
        bigSansFont = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 20)

        # Background
        angle = 0.0
        angleStep = 360.0 / numBins
        for i in range(0, numBins, 1):
            draw.pieslice((int(imageorigin[0] - radius), int(imageorigin[1] - radius), int(imageorigin[0] + radius),
                           int(imageorigin[1] + radius)), int(angle + 90), int(angle + angleStep + 90),
                          fill=(255, int(255 * (1 - buckets[i])), 255))
            angle += angleStep

        # Compass points
        labels = ['N', 'E', 'S', 'W']

        for i in range(0, 4, 1):
            angle = i * math.radians(90) + math.radians(180)

            # Major tic
            startPoint = (
            imageorigin[0] - radius * math.sin(angle) * 0.93, imageorigin[1] + radius * math.cos(angle) * 0.93)
            endPoint = (imageorigin[0] - radius * math.sin(angle), imageorigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=(0, 0, 0))

            labelText = labels[i]
            stringSize = sansFont.getsize(labelText)

            labelPoint = (
            imageorigin[0] - radius * math.sin(angle) * 0.80, imageorigin[1] + radius * math.cos(angle) * 0.80)
            labelPoint = (labelPoint[0] - stringSize[0] / 2, labelPoint[1] - stringSize[1] / 2)

            draw.text(labelPoint, labelText, font=sansFont, fill=(0, 0, 0))

            # Minor tic
            angle += math.radians(45)
            startPoint = (
            imageorigin[0] - radius * math.sin(angle) * 0.93, imageorigin[1] + radius * math.cos(angle) * 0.93)
            endPoint = (imageorigin[0] - radius * math.sin(angle), imageorigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=(0, 0, 0))

        # The needle
        angle = math.radians(windDirNow)
        endPoint = (imageorigin[0] - radius * math.sin(angle) * 0.7, imageorigin[1] + radius * math.cos(angle) * 0.7)
        leftPoint = (imageorigin[0] - radius * math.sin(angle - math.pi * 7 / 8) * 0.2,
                     imageorigin[1] + radius * math.cos(angle - math.pi * 7 / 8) * 0.2)
        rightPoint = (imageorigin[0] - radius * math.sin(angle + math.pi * 7 / 8) * 0.2,
                      imageorigin[1] + radius * math.cos(angle + math.pi * 7 / 8) * 0.2)
        midPoint = (imageorigin[0] - radius * math.sin(angle + math.pi) * 0.1,
                    imageorigin[1] + radius * math.cos(angle + math.pi) * 0.1)

        draw.line((leftPoint, endPoint), fill=(3, 29, 219))
        draw.line((rightPoint, endPoint), fill=(3, 29, 219))
        draw.line((leftPoint, midPoint), fill=(3, 29, 219))
        draw.line((rightPoint, midPoint), fill=(3, 29, 219))

        # Outline
        draw.ellipse(((imageorigin[0] - radius, imageorigin[1] - radius),
                      (imageorigin[0] + radius, imageorigin[1] + radius)), outline=(0, 0, 0))

        # Digital value text
        degreeSign = u'\N{DEGREE SIGN}'
        digitalText = "%d" % windDirNow + degreeSign
        stringSize = bigSansFont.getsize(digitalText)
        draw.text((imageorigin[0] - stringSize[0] / 2, imageorigin[1] + radius * 0.4 - stringSize[1] / 2), digitalText,
                  font=bigSansFont, fill=(3, 29, 219))

        del draw

        im.save(self.wheretosaveit + gaugename + "Gauge.png", "PNG")

    def histogram(self, gaugeName, fieldName):
        #
        # Currently this function only works for temperature and converts it into Celcius
        #

        # TODO:
        #      1) lookup fieldName from gaugelist
        #      2) Deal with non Metric units a lot better

        # Metric or imperial units
        isUS = False
        if "US" == self.config_dict['StdConvert']['target_unit']:
            syslog.syslog(syslog.LOG_DEBUG, "reportengine: US units detected")
            isUS = True

        minVal = self.gauge_dict[gaugeName].as_float('minvalue')
        maxval = self.gauge_dict[gaugeName].as_float('maxvalue')
        numBins = self.gauge_dict[gaugeName].as_int('bins')

        buckets = [0.0] * numBins
        bucketSpan = (maxval - minVal) / numBins

        # One data point recorded every 5 mins for 'history' number of hours
        numPoints = self.gauge_dict[gaugeName].as_int('history') * 60 / 5

        archive_db = self.config_dict['StdArchive']['archive_database']
        archive = weewx.archive.Archive.open(self.config_dict['Databases'][archive_db])

        roof = 0

        for row in archive.genSql("SELECT " + fieldName + " FROM archive ORDER BY dateTime DESC LIMIT %d" % numPoints):
            if row[0] is not None:
                histValue = float(row[0])

                # Convert archive units from F into C?
                if isUS is True:
                    histValue = (histValue - 32) * 5 / 9

                if histValue > maxval:
                    syslog.syslog(syslog.LOG_DEBUG,
                                  "histogram: %s = %f is higher than maxvalue (%f)" % (fieldName, histValue, maxval))
                elif histValue < minVal:
                    syslog.syslog(syslog.LOG_DEBUG,
                                  "histogram: %s = %f is lower than minvalue (%f)" % (fieldName, histValue, minVal))
                else:
                    bucketNum = int((histValue - minVal) / bucketSpan)
                    buckets[bucketNum] += 1.0

                    if buckets[bucketNum] > roof:
                        roof = buckets[bucketNum]

        buckets = [i / roof for i in buckets]

        return buckets

    def drawGauge(self, gaugeValue, gaugeName):
        imageWidth = self.gauge_dict.as_int('image_width')
        imageHeight = self.gauge_dict.as_int('image_height')
        imageOrigin = (imageWidth / 2, imageHeight / 2)

        digitalText = None

        # Check gaugeValue is usable
        if gaugeValue is None:
            syslog.syslog(syslog.LOG_INFO, "reportengine: Generating %s gauge, (%d x %d), value = None" % (
            gaugeName, imageWidth, imageHeight))
            digitalText = "N/A"
        else:
            syslog.syslog(syslog.LOG_INFO, "reportengine: Generating %s gauge, (%d x %d), value = %.1f" % (
            gaugeName, imageWidth, imageHeight, gaugeValue))

            if gaugeName == "Temperature":
            # Temparature scale
                degreeSign = u'\N{DEGREE SIGN}'
                digitalText = "%.1f" % gaugeValue + degreeSign + "C"
            elif gaugeName == "Pressure":
                digitalText = "%d" % gaugeValue + " mbar"
            elif gaugeName == "Humidity":
                digitalText = "%d" % gaugeValue + "%"
            elif gaugeName == "WindSpeed":
                digitalText = "%.1f" % gaugeValue + " mph"
            elif gaugeName == "WindGust":
                digitalText = "%.1f" % gaugeValue + " mph"

        minVal = self.gauge_dict[gaugeName].as_float('minvalue')
        maxval = self.gauge_dict[gaugeName].as_float('maxvalue')
        majorStep = self.gauge_dict[gaugeName].as_float('majorstep')
        minorStep = self.gauge_dict[gaugeName].as_float('minorstep')
        labelFontSize = self.gauge_dict[gaugeName].as_int('labelfontsize')
        labelFormat = "%d"

        minAngle = 45 # in degrees
        maxAngle = 315

        im = Image.new("RGB", (imageWidth, imageHeight), (255, 255, 255))

        draw = ImageDraw.Draw(im)

        if imageWidth < imageHeight:
            radius = imageWidth * 0.45
        else:
            radius = imageHeight * 0.45

        # Background
        if gaugeName == "Temperature":
            if self.gauge_dict[gaugeName].as_int('history') > 0:

                numBins = self.gauge_dict[gaugeName].as_int('bins')
                buckets = self.histogram(gaugeName, "outTemp")

                angle = float(minAngle)
                angleStep = (maxAngle - minAngle) / float(numBins)
                for i in range(0, numBins, 1):
                    draw.pieslice(
                        (int(imageOrigin[0] - radius), int(imageOrigin[1] - radius), int(imageOrigin[0] + radius),
                         int(imageOrigin[1] + radius)), int(angle + 90), int(angle + angleStep + 90),
                        fill=(255, int(255 * (1 - buckets[i])), 255))
                    angle += angleStep

        draw.ellipse(((imageOrigin[0] - radius, imageOrigin[1] - radius),
                      (imageOrigin[0] + radius, imageOrigin[1] + radius)), outline=(0, 0, 0))

        sansFont = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", labelFontSize)
        bigSansFont = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 20)

        labelValue = minVal

        # Major tic marks and scale labels
        for angle in frange(math.radians(minAngle), math.radians(maxAngle), int(1 + (maxval - minVal) / majorStep)):
            startPoint = (
            imageOrigin[0] - radius * math.sin(angle) * 0.93, imageOrigin[1] + radius * math.cos(angle) * 0.93)
            endPoint = (imageOrigin[0] - radius * math.sin(angle), imageOrigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=(0, 0, 0))

            labelText = str(labelFormat % labelValue)
            stringSize = sansFont.getsize(labelText)

            labelPoint = (
            imageOrigin[0] - radius * math.sin(angle) * 0.80, imageOrigin[1] + radius * math.cos(angle) * 0.80)
            labelPoint = (labelPoint[0] - stringSize[0] / 2, labelPoint[1] - stringSize[1] / 2)

            draw.text(labelPoint, labelText, font=sansFont, fill=(0, 0, 0))
            #draw.point(labelPoint)
            labelValue += majorStep

        # Minor tic marks
        for angle in frange(math.radians(minAngle), math.radians(maxAngle), int(1 + (maxval - minVal) / minorStep)):
            startPoint = (
            imageOrigin[0] - radius * math.sin(angle) * 0.97, imageOrigin[1] + radius * math.cos(angle) * 0.97)
            endPoint = (imageOrigin[0] - radius * math.sin(angle), imageOrigin[1] + radius * math.cos(angle))
            draw.line((startPoint, endPoint), fill=(0, 0, 0))

        # The needle
        if gaugeValue is not None:
            angle = math.radians(minAngle + (gaugeValue - minVal) * (maxAngle - minAngle) / (maxval - minVal))
            endPoint = (
            imageOrigin[0] - radius * math.sin(angle) * 0.7, imageOrigin[1] + radius * math.cos(angle) * 0.7)
            leftPoint = (imageOrigin[0] - radius * math.sin(angle - math.pi * 7 / 8) * 0.2,
                         imageOrigin[1] + radius * math.cos(angle - math.pi * 7 / 8) * 0.2)
            rightPoint = (imageOrigin[0] - radius * math.sin(angle + math.pi * 7 / 8) * 0.2,
                          imageOrigin[1] + radius * math.cos(angle + math.pi * 7 / 8) * 0.2)
            midPoint = (imageOrigin[0] - radius * math.sin(angle + math.pi) * 0.1,
                        imageOrigin[1] + radius * math.cos(angle + math.pi) * 0.1)

            draw.line((leftPoint, endPoint), fill=(3, 29, 219))
            draw.line((rightPoint, endPoint), fill=(3, 29, 219))
            draw.line((leftPoint, midPoint), fill=(3, 29, 219))
            draw.line((rightPoint, midPoint), fill=(3, 29, 219))

        # Digital value text
        stringSize = bigSansFont.getsize(digitalText)
        draw.text((imageOrigin[0] - stringSize[0] / 2, imageOrigin[1] + radius * 0.4 - stringSize[1] / 2), digitalText,
                  font=bigSansFont, fill=(3, 29, 219))

        del draw

        im.save(self.wheretosaveit + gaugeName + "Gauge.png", "PNG")

    def getRecord(self, archivedb, time_ts):
        """Get an observation record from the archive database, returning
        it as a ValueDict."""

        # Get the record...:
        record_dict = archivedb.getRecord(time_ts)
        # ... convert to a dictionary with ValueTuples as values...
        record_dict_vt = dictFromStd(record_dict)
        # ... then wrap it in a ValueDict:
        record_vd = ValueDict(record_dict_vt, context='current',
                                          formatter=self.formatter, converter=self.converter)

        return record_vd


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
