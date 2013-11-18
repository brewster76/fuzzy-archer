#
# Code for creating html historic data tables in a nice colour scheme.
#
# Tested with weewx 2.5.0.
# 
# Nick Dajda, based on code from the weewx distribution. Nov 2013.

"""Extends the search list used by the Cheetah generator, based on weewx example
code.

To use it, modify the option search_list in your skin.conf configuration file,
adding the name of this extension. For this example, the name of the extension
is user.generator.MyXSearch. So, when you're done, it will look something
like this:

[CheetahGenerator]
    search_list_extensions = user.generator.MyXSearch

1) The alltime tag: 

Allows tags such as $alltime.outTemp.max for the all-time max
temperature, or $seven_day.rain.sum for the total rainfall in the last
seven days.

2) Nice colourful tables summarising history data by month and year.

Adding the section below to your skins.conf file will create these new tags:
   $min_temp_table
   $max_temp_table
   $avg_temp_table
   $rain_table

Written for metric users so temperature is converted to degC, pressure is mbar 
and rain is mm.

#
# Settings for Nick's HTML month/year summary table summary generator
#
[TableGenerator]

    # minvalues, maxvalues and colours should contain the same number of elements.
    # e.g. in the [min_temp] example below, if the minimum temperature measured in 
    #      a month is between -50 and -10 (degC) then the cell will be shaded
    #      in html colour code #0029E5.
    #
    # sqlquery text below works for sqlite but may not work for other databases.

    [[min_temp]]
        minvalues = -50, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35
        maxvalues =  -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 60
        colours =   "#0029E5", "#0186E7", "#02E3EA", "#04EC97", "#05EF3D2, "#2BF207", "#8AF408", "#E9F70A", "#F9A90B", "#FC4D0D", "#FF0F2D"
        sqlquery = "SELECT strftime('%Y', datetime(dateTime, 'unixepoch', 'localtime')) as Year, strftime('%m', datetime(dateTime, 'unixepoch', 'localtime')) as Month, MIN(min) FROM outTemp GROUP BY Year, Month"
        units = temperature

    [[max_temp]]
        minvalues = -50, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35
        maxvalues =  -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 60
        colours =   "#0029E5", "#0186E7", "#02E3EA", "#04EC97", "#05EF3D2, "#2BF207", "#8AF408", "#E9F70A", "#F9A90B", "#FC4D0D", "#FF0F2D"
        sqlquery = "SELECT strftime('%Y', datetime(dateTime, 'unixepoch', 'localtime')) as Year, strftime('%m', datetime(dateTime, 'unixepoch', 'localtime')) as Month, MAX(max) FROM outTemp GROUP BY Year, Month"
        units = temperature

    [[avg_temp]]
        minvalues = -50, -10, -5, 0, 5, 10, 15, 20, 25, 30, 35
        maxvalues =  -10, -5, 0, 5, 10, 15, 20, 25, 30, 35, 60
        colours =   "#0029E5", "#0186E7", "#02E3EA", "#04EC97", "#05EF3D2, "#2BF207", "#8AF408", "#E9F70A", "#F9A90B", "#FC4D0D", "#FF0F2D"
        sqlquery = "SELECT strftime('%Y', datetime(dateTime, 'unixepoch', 'localtime')) as Year, strftime('%m', datetime(dateTime, 'unixepoch', 'localtime')) as Month, SUM(sum) / SUM(count) FROM outTemp GROUP BY Year, Month"
        units = temperature

    [[rain]]
        minvalues = 0, 25, 50, 75, 100, 150
        maxvalues = 25, 50, 75, 100, 150, 1000
        colours = "#E0F8E0", "#A9F5A9", "#58FA58", "#2EFE2E", "#01DF01", "#01DF01"
        sqlquery = "SELECT strftime('%Y', datetime(dateTime, 'unixepoch', 'localtime')) as Year, strftime('%m', datetime(dateTime, 'unixepoch', 'localtime')) as Month, SUM(sum) FROM rain GROUP BY Year, Month"
        units = rain
"""

import datetime
import time
from operator import itemgetter

from weewx.cheetahgenerator import SearchList
from weewx.stats import TimeSpanStats
from weeutil.weeutil import TimeSpan
from weewx.units import conversionDict

class MyXSearch(SearchList):                                           
    
    def __init__(self, generator):                                     
        SearchList.__init__(self, generator)
        self.table_dict = generator.skin_dict['TableGenerator']

    def get_extension(self, valid_timespan, archivedb, statsdb):       
        """Returns a search list extension with two additions.
        
        Parameters:
          valid_timespan: An instance of weeutil.weeutil.TimeSpan. This will
                          hold the start and stop times of the domain of 
                          valid times.

          archivedb: An instance of weewx.archive.Archive
          
          statsdb:   An instance of weewx.stats.StatsDb
        """

        # First, get a TimeSpanStats object for all time. This one is easy
        # because the object valid_timespan already holds all valid times to be
        # used in the report.
        all_stats = TimeSpanStats(valid_timespan,
                                  statsdb,
                                  formatter=self.generator.formatter,
                                  converter=self.generator.converter)  

        # Now create a small dictionary with keys 'alltime' and 'seven_day':
        search_list_extension = {'alltime' : all_stats}             

        for table in self.table_dict:
            search_list_extension[table + '_table'] = self.statsHTMLTable(table, self.table_dict[table]['sqlquery'], self.table_dict[table]['units'], statsdb)
        
        return search_list_extension

    def colorCell(self, value, units, bgColours):
        cellText = "<td"

        # Temperature needs converting from F to C
        if 'temperature' == units:
            value = conversionDict['degree_F']['degree_C'](value)
        elif 'rain' == units:
            value = conversionDict['inch']['mm'](value)
        elif 'pressure' == units:
            value = conversionDict['inHg']['mbar'](value)

        for c in bgColours:
            if (value >= int(c[0])) and (value <= int(c[1])):
                cellText += " bgcolor = \"%s\"" % c[2]

        if 'temperature' == units:
            cellText += "> %.1f </td>" % value
        else:
            cellText += "> %.2f </td>" % value

        return cellText

    def statsHTMLTable(self, table, sqlQuery, units, statsdb):

        recordListRaw = []

        bgColours = zip(self.table_dict[table]['minvalues'], self.table_dict[table]['maxvalues'], self.table_dict[table]['colours'])

        cursor = statsdb.connection.cursor()
        try:
            for row in cursor.execute(sqlQuery):
                record = (int(row[0]), int(row[1]), row[2])
                recordListRaw.append(record)
        finally:
            cursor.close()

        #for row in statsdb.genSql(sqlQuery):

        recordListSorted = sorted(recordListRaw, key=itemgetter(0, 1))

        year = month = None
        htmlText = """<table class="table">

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
        htmlLine = None

        for record in recordListSorted:
            if record[0] != year:              
                if year is not None: 
                    # End of a year... Pad out and move onto the next one
                    for i in range(12 - month):
                        htmlLine += (' ' * 12) + "<td>-</td>\n"

                    htmlLine += (' ' * 8) + "</tr>\n"
                    htmlText += htmlLine

                year = record[0]

                # Start a new line
                htmlLine = (' ' * 8) + "<tr>\n"
                htmlLine += (' ' * 12) + "<td>%d</td>\n" % year

                month = 0
            
            # Any padding needed?
            for i in range(record[1] - month - 1):
                # Empty cell
                htmlLine += (' ' * 12) + "<td>-</td>\n"

            month = record[1]
            htmlLine += (' ' * 12) + self.colorCell(record[2], units, bgColours)

        # Any padding required?
        for i in range(12 - month):
            htmlLine += (' ' * 12) + "<td>-</td>\n"

        htmlLine += (' ' * 8) + "</tr>\n"
        htmlLine += (' ' * 4) + "</tbody>\n"
        htmlLine += "</table>\n"

        htmlText += htmlLine

        return htmlText
