# installer for the bootstrap skin.
#
# Based on installer for xstats
#
# Configured by Nick and Michael to install bootstrap skin, 2014-2023

import os.path
import configobj

import setup

def loader():
    return BootstrapInstaller()

class BootstrapInstaller(setup.ExtensionInstaller):
    _skin_conf_files = ['Bootstrap/skin.conf']

    def __init__(self):
        files=[('skins/Bootstrap',
            ['skins/Bootstrap/about.html.tmpl',
             'skins/Bootstrap/chartimages.html.inc',
             'skins/Bootstrap/day.html.tmpl',
             'skins/Bootstrap/foot.html.inc',
             'skins/Bootstrap/graphMenu.html.inc',
             'skins/Bootstrap/head.html.inc',
             'skins/Bootstrap/history.html.tmpl',
             'skins/Bootstrap/index.html.tmpl',
             'skins/Bootstrap/livegauges.html.inc',
             'skins/Bootstrap/location.html.inc',
             'skins/Bootstrap/month.html.tmpl',
             'skins/Bootstrap/moonphase.html.inc',
             'skins/Bootstrap/nav.html.inc',
             'skins/Bootstrap/news.html.tmpl',
             'skins/Bootstrap/script.html.inc',
             'skins/Bootstrap/stats.html.tmpl',
             'skins/Bootstrap/sunRiseSet.html.inc',
             'skins/Bootstrap/uptime.html.inc',
             'skins/Bootstrap/week.html.tmpl',
             'skins/Bootstrap/year.html.tmpl',
             'skins/Bootstrap/reportData.json.tmpl',
             'skins/Bootstrap/rain.html.inc',
             'skins/Bootstrap/stationInfo.json.inc',
             'skins/Bootstrap/skin.conf']),
           ('skins/Bootstrap/NOAA',
            ['skins/Bootstrap/NOAA/NOAA-YYYY.txt.tmpl',
             'skins/Bootstrap/NOAA/NOAA-YYYY-MM.txt.tmpl']),
           ('skins/Bootstrap/font',
            ['skins/Bootstrap/font/FreeMonoBold.ttf',
            'skins/Bootstrap/font/GNU_FreeFont.txt',
            'skins/Bootstrap/font/Kanit-Bold.ttf',
            'skins/Bootstrap/font/Kanit-Regular.ttf',
            'skins/Bootstrap/font/OFL.txt']),
           ('bin/user',
            ['bin/user/historygenerator.py',
             'bin/user/jsonengine.py',
             'bin/user/largeimagegenerator.py',
             'bin/user/sunevents.py']),
           ('skins/Bootstrap/css',
            ['skins/Bootstrap/css/bootstrap.min.css',
             'skins/Bootstrap/css/bootstrap-icons.min.css',
             'skins/Bootstrap/css/live.css']),
           ('skins/Bootstrap/css/fonts',
            ['skins/Bootstrap/css/fonts/bootstrap-icons.woff',
             'skins/Bootstrap/css/fonts/bootstrap-icons.woff2']),
           ('skins/Bootstrap/js',
            ['skins/Bootstrap/js/bootstrap.bundle.min.js',
            'skins/Bootstrap/js/charts.js',
            'skins/Bootstrap/js/echarts.min.js',
             'skins/Bootstrap/js/jquery.min.js',
            'skins/Bootstrap/js/gauges.js',
            'skins/Bootstrap/js/lang.js',
            'skins/Bootstrap/js/mqtt.min.js',
            'skins/Bootstrap/js/luxon.min.js',
            'skins/Bootstrap/js/site.js',
            'skins/Bootstrap/js/units.js']),
           ('skins/Bootstrap/lang',
            ['skins/Bootstrap/lang/cz.conf',
             'skins/Bootstrap/lang/de.conf',
             'skins/Bootstrap/lang/en.conf',
             'skins/Bootstrap/lang/es.conf',
             'skins/Bootstrap/lang/fr.conf',
             'skins/Bootstrap/lang/gr.conf',
             'skins/Bootstrap/lang/it.conf',
             'skins/Bootstrap/lang/nl.conf',
             'skins/Bootstrap/lang/no.conf',
             'skins/Bootstrap/lang/th.conf',
             'skins/Bootstrap/lang/zh.conf'])]

        version="4.4"
        super(BootstrapInstaller, self).__init__(
            version=version,
            name='bootstrap',
            description='A skin based around the bootstrap framework',
            author="Nick Dajda, Michael Kainzbauer and other contributors",
            author_email="nick.dajda@gmail.com",
            config={
                'StdReport': {
                    'Bootstrap': {
                        'skin':'Bootstrap',
                        'enable':'true',
                        'lang':'en',
                        'HTML_ROOT':'Bootstrap'}}},
            files=files)

        print("")
        print("The following alternative languages are available:")
        self.language = None

        for f in files:
            if f[0] == 'skins/Bootstrap/lang':
                for language in f[1]:
                    l = language.strip('conf').split('/')[-1]
                    print(("   %s" % l[:-1]))

        print("")
        print("Change to a different language following the description at:")
        print("   http://www.weewx.com/docs/customizing.htm#localization")

        print("")
        print("Default location for HTML and image files is public_html/Bootstrap")
        print("*** POINT YOUR BROWSER TO: public_html/Bootstrap/index.html ***")
        print("")
