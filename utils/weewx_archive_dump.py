#!/usr/bin/python
#
# Turn a weewx database into a CSV file.
#
import datetime 
import sqlite3 as lite
import shutil

# Where your archive database is (sqlite only)
sourceFile = '/home/weewx/archive/weewx.sdb'

# Where to copy the file so weewx doesn't hang while we lock the database
tempFile = '/tmp/weewx.sdb.dump'

shutil.copy (sourceFile, tempFile)

con = lite.connect(tempFile)

with open('/home/pi/dump.csv', 'w') as f:
   con.row_factory = lite.Row

   f.write ("date + time, dateTime, usUnits, interval, barometer, outTemp, inHumidity, outHumidity, windSpeed, " +
            "windDir, windGust, windGustDir, rainRate, rain, dewpoint, windchill, heatindex, rxCheckPercent\n")

   cur = con.cursor()
   cur.execute("SELECT * FROM archive")

   while True:
      row = cur.fetchone()
      if not row: break

      dateString = datetime.datetime.fromtimestamp(row["dateTime"]).strftime("%Y-%m-%d %H:%M:%S")
      f.write ("%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s\n" % ( dateString, row['dateTime'],
            row['usUnits'], row['interval'], row['barometer'], row['outTemp'], row['inHumidity'], row['outHumidity'],
            row['windSpeed'], row['windDir'],  row['windGust'], row['windGustDir'], row['rainRate'], row['rain'],
            row['dewpoint'], row['windchill'], row['heatindex'], row['rxCheckPercent']))

