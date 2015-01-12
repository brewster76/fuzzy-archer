#
# Code for creating html historic data tables in a nice colour scheme.
#
# Nick Dajda, based on code from the weewx distribution. Nov 2013.

"""Extends the search list used by the Cheetah generator, based on weewx example
code.

Tested on Weewx release 3.0.1.
Tested with sqlite, may not work with other databases.

WILL NOT WORK WITH Weewx prior to release 3.0.
  -- Use this version for 2.4 - 2.7:  https://github.com/brewster76/fuzzy-archer/releases/tag/v2.0

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

import time
from operator import itemgetter

from weewx.cheetahgenerator import SearchList
from weewx.tags import TimespanBinder
from weewx.units import conversionDict
import weeutil.weeutil

class MyXSearch(SearchList):
    
    def __init__(self, generator):                                     
        SearchList.__init__(self, generator)
        self.table_dict = generator.skin_dict['TableGenerator']

        # Calculate the tables once every refresh_interval mins
        self.refresh_interval = int(self.table_dict.get('refresh_interval', 5))
        self.cache_time = 0
        self.search_list_extension = {}

        # Make bootstrap specific labels in config file available to
        try:
            bootstrap_labels = generator.skin_dict['BootstrapLabels']
        except:
            # TODO: Use logger function for this 
            print "No bootstrap specific labels found"
        else:
            for bootstrap_label in bootstrap_labels:
                self.search_list_extension['bootstrap_' + bootstrap_label] = \
                    generator.skin_dict['BootstrapLabels'][bootstrap_label]

    def get_extension_list(self, valid_timespan, db_lookup):
        """For weewx V3.x extensions. Should return a list
        of objects whose attributes or keys define the extension.

        timespan:  An instance of weeutil.weeutil.TimeSpan. This will hold the
                   start and stop times of the domain of valid times.

        db_lookup: A function with call signature db_lookup(data_binding), which
        returns a database manager and where data_binding is an optional binding
        name. If not given, then a default binding will be used.
        """

        # Recalculate when 60 mins passed
        if (time.time() - (self.refresh_interval * 60)) > self.cache_time:
            self.cache_time = time.time()

            # First, get a TimeSpanStats object for all time. This one is easy
            # because the object valid_timespan already holds all valid times to be
            # used in the report.
            all_stats = TimespanBinder(valid_timespan, db_lookup, formatter=self.generator.formatter,
                                      converter=self.generator.converter)

            # Now create a small dictionary with keys 'alltime' and 'seven_day':
            self.search_list_extension['alltime'] = all_stats

            for table in self.table_dict.sections:
                table_options = weeutil.weeutil.accumulateLeaves(self.table_dict[table])
                self.search_list_extension[table + '_table'] = self.statsHTMLTable(table_options, db_lookup)

        return [self.search_list_extension]

    def colorCell(self, value, units, bgColours):

        if value is not None:
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

        else:
            cellText = "<td>-</td>\n"

        return cellText

    def statsHTMLTable(self, table_options, db_lookup):
        recordListRaw = []

        bgColours = zip(table_options['minvalues'], table_options['maxvalues'], table_options['colours'])

        db_manager = self.generator.db_binder.get_manager()

        for row in db_manager.genSql(table_options['sqlquery']):
            record = (int(row[0]), int(row[1]), row[2])
            recordListRaw.append(record)

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
            htmlLine += (' ' * 12) + self.colorCell(record[2], table_options['units'], bgColours)

        # Any padding required?
        for i in range(12 - month):
            htmlLine += (' ' * 12) + "<td>-</td>\n"

        htmlLine += (' ' * 8) + "</tr>\n"
        htmlLine += (' ' * 4) + "</tbody>\n"
        htmlLine += "</table>\n"

        htmlText += htmlLine

        return htmlText
