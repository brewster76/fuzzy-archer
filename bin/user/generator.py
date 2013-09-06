#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision: 730 $
#    $Author: tkeffer $
#    $Date: 2012-11-03 10:58:13 -0700 (Sat, 03 Nov 2012) $
#

"""Example of how to extend a report generator.

This generator offers two extra tags:

    'alltime': All time statistics. For example, "what is the all time high temperature?"

    'seven_day': Statistics for the last seven days. That is, since midnight seven days
                 ago.

To use it, in the skin's generator_list, replace weewx.filegenerator.FileGenerator
with examples.mygenerator.MyFileGenerator.

You can then use tags such as $alltime.outTemp.max for the all-time max temperature,
or $seven_day.rain.sum for the total rainfall in the last seven days.
"""
import datetime
import time
import syslog
from operator import itemgetter, attrgetter

import weewx.archive

from weewx.filegenerator import FileGenerator
from weewx.stats import TimeSpanStats
from weeutil.weeutil import TimeSpan
from weeutil.weeutil import genMonthSpans
from weewx.units import conversionDict

class MyFileGenerator(FileGenerator):                            
  
    def getToDateSearchList(self, archivedb, statsdb, valid_timespan): 
        """Returns a search list with two additions. Overrides the
        default "getToDateSearchList" method.
        
        Parameters:
          archivedb: An instance of weewx.archive.Archive
          
          statsdb:   An instance of weewx.stats.StatsDb
          
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of 
                          valid times."""

        # First, get a TimeSpanStats object for all time. This one is easy
        # because the object valid_timespan already holds all valid times to be
        # used in the report.
        all_stats = TimeSpanStats(valid_timespan,
                                  statsdb,
                                  formatter=self.formatter,
                                  converter=self.converter)         
        
        # Now get a TimeSpanStats object for the last seven days. This one we
        # will have to calculate. First, calculate the time at midnight, seven
        # days ago. The variable week_dt will be an instance of datetime.date.
        week_dt = datetime.date.fromtimestamp(valid_timespan.stop) - datetime.timedelta(weeks=1)   
        # Now convert it to unix epoch time:
        week_ts = time.mktime(week_dt.timetuple())                  
        # Now form a TimeSpanStats object, using the time span we just calculated:
        seven_day_stats = TimeSpanStats(TimeSpan(week_ts, valid_timespan.stop),
                                        statsdb,
                                        formatter=self.formatter,
                                        converter=self.converter)  

        #
        # High, low and average temperatures for every month
        #
        self.bgColours = [(-50, -10, "#2E64FE"), 
                         (-10, 0, "#81BEF7"),
                         (0, 10, "#81F79F"),
                         (10, 20, "#58FA58"),
                         (20, 30, "#F3F781"),
                         (30, 60, "#F78181")]

        recordListRaw = []

        for row in archivedb.genSql("SELECT strftime('%Y', datetime(dateTime, 'unixepoch')) as Year, strftime('%m', datetime(dateTime, 'unixepoch')) as Month, MIN(outTemp), MAX(outTemp), AVG(outTemp) FROM archive GROUP BY Year, Month"):
#            record = {'year': int(row[1]), 'month': int(row[0]), 'max': row[2], 'min': row[3], 'avg': row[4]}
            record = (int(row[0]), int(row[1]), row[2], row[3], row[4])
            recordListRaw.append(record)
        
        recordListSorted = sorted(recordListRaw, key=itemgetter(0, 1))

        year = month = None
        html_min = html_max = """<table class="table table-hover">
    <thead>
        <tr>
            <th></th>
            <th>Jan</th>
            <th>Feb</th>
            <th>Mar</th>
            <th>Apr</th>
            <th>May</th>
            <th>Jun</th>
            <th>Jul</th>
            <th>Aug</th>
            <th>Sep</th>
            <th>Oct</th>
            <th>Nov</th>
            <th>Dec</th>
        </tr>
    </thead>
    <tbody>
"""

        for record in recordListSorted:
            if record[0] != year:              
                if year is not None: 
                    # End of a year... Pad out and move onto the next one
                    for i in range(12 - month):
                        htmlLine_min += (' ' * 12) + "<td>-</td>\n"
                        htmlLine_max += (' ' * 12) + "<td>-</td>\n"

                    htmlLine_min += (' ' * 8) + "</tr>\n"
                    htmlLine_max += (' ' * 8) + "</tr>\n"

                    html_min += htmlLine_min
                    html_max += htmlLine_max

                year = record[0]

                # Start a new line
                htmlLine_min = (' ' * 8) + "<tr>\n"
                htmlLine_min += (' ' * 12) + "<td>%d</td>\n" % year

                htmlLine_max = (' ' * 8) + "<tr>\n"
                htmlLine_max += (' ' * 12) + "<td>%d</td>\n" % year

                month = 0
            
            # Any padding needed?
            for i in range(record[1] - month - 1):
                # Empty cell
                htmlLine_min += (' ' * 12) + "<td>-</td>\n"
                htmlLine_max += (' ' * 12) + "<td>-</td>\n"

            month = record[1]

            htmlLine_min += (' ' * 12) + self.colorCell(conversionDict['degree_F']['degree_C'](record[2]))
            htmlLine_max += (' ' * 12) + self.colorCell(conversionDict['degree_F']['degree_C'](record[3]))


        # Any padding required?
        for i in range(12 - month):
            htmlLine_min += (' ' * 12) + "<td>-</td>\n"
            htmlLine_max += (' ' * 12) + "<td>-</td>\n"

        htmlLine_min += (' ' * 8) + "</tr>\n"
        htmlLine_min += (' ' * 4) + "</tbody>\n"
        htmlLine_min += "</table>\n"

        htmlLine_max += (' ' * 8) + "</tr>\n"
        htmlLine_max += (' ' * 4) + "</tbody>\n"
        htmlLine_max += "</table>\n"

        html_min += htmlLine_min
        html_max += htmlLine_max
        
        # Get the superclass's search list:     
        search_list = FileGenerator.getToDateSearchList(self, archivedb, statsdb, valid_timespan) 

        # Now tack on my two additions as a small dictionary with keys 'alltime' and 'seven_day':
        search_list += [ {'alltime'        : all_stats,
                          'seven_day'      : seven_day_stats,
                          'min_temp_table' : html_min,
                          'max_temp_table' : html_max} ]               

        return search_list

    def colorCell(self, temperature):
        cellText = "<td"

        for c in self.bgColours:
            if (temperature >= c[0]) and (temperature <= c[1]):
                cellText += " bgcolor = \"%s\"" % c[2]

        cellText += "> %.1f </td>" % temperature

        return cellText


#
# What is this...?
#
    def notNeeded(self):
        f = open("/tmp/search_list", 'w')
        f.write ("%s\n" % search_list)

        yearNow = 0
        monthNow = 0

        for span in genMonthSpans(valid_timespan.start, valid_timespan.stop):          
            startOfMonth = datetime.datetime.fromtimestamp(span[0])

            if yearNow <> startOfMonth.year:
                print "New year: ", startOfMonth.year
                yearNow = startOfMonth.year
            
            print startOfMonth.month

