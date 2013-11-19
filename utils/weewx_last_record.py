#!/usr/bin/python

# Prints the last logged record in the weewx database


import datetime 
import sqlite3 as lite
import shutil

sourceFile = '/home/weewx/archive/weewx.sdb'

con = lite.connect(sourceFile)

con.row_factory = lite.Row

print "date + time, dateTime, usUnits, interval, barometer, inTemp, outTemp, inHumidity, outHumidity, windSpeed, windDir, windGust, windGustDir, rainRate, rain, dewpoint, windchill, heatindex, rxCheckPercent"

cur = con.cursor()
cur.execute("SELECT * FROM archive ORDER BY dateTime DESC LIMIT 1")

while True:
   row = cur.fetchone()
   if not row: break

   dateString = datetime.datetime.fromtimestamp(row["dateTime"]).strftime("%Y-%m-%d %H:%M:%S")
   print "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s\n" % ( dateString, row['dateTime'],
         row['usUnits'], row['interval'], row['barometer'], row['inTemp'], row['outTemp'], row['inHumidity'], row['outHumidity'],
         row['windSpeed'], row['windDir'],  row['windGust'], row['windGustDir'], row['rainRate'], row['rain'],
         row['dewpoint'], row['windchill'], row['heatindex'], row['rxCheckPercent'])

