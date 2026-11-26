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
    _version="4.4"

    def __init__(self):
        files=[('skins/Bootstrap',
            ['skins/Bootstrap/about.html.tmpl',
             'skins/Bootstrap/foot.html.inc',
             'skins/Bootstrap/graphMenu.html.inc',
             'skins/Bootstrap/head.html.inc',
             'skins/Bootstrap/history.html.tmpl',
             'skins/Bootstrap/images.html.inc',
             'skins/Bootstrap/index.html.tmpl',
             'skins/Bootstrap/livegauges.html.inc',
             'skins/Bootstrap/location.html.inc',
             'skins/Bootstrap/moonphase.html.inc',
             'skins/Bootstrap/nav.html.inc',
             'skins/Bootstrap/news.html.tmpl',
             'skins/Bootstrap/periodview.html.inc',
             'skins/Bootstrap/script.html.inc',
             'skins/Bootstrap/stats.html.tmpl',
             'skins/Bootstrap/sunRiseSet.html.inc',
             'skins/Bootstrap/uptime.html.inc',
             'skins/Bootstrap/reportData.json.tmpl',
             'skins/Bootstrap/rain.html.inc',
             'skins/Bootstrap/stationInfo.json.inc',
             'skins/Bootstrap/skin.conf']),
           ('skins/Bootstrap/NOAA',
            ['skins/Bootstrap/NOAA/NOAA-YYYY.txt.tmpl',
             'skins/Bootstrap/NOAA/NOAA-YYYY-MM.txt.tmpl']),
           ('bin/user',
            ['bin/user/historyaggregate.py',
             'bin/user/historybackfill.py',
             'bin/user/historyconfig.py',
             'bin/user/historydata.py',
             'bin/user/historygenerator.py',
             'bin/user/historyperiods.py',
             'bin/user/historyregen.py',
             'bin/user/historywriter.py',
             'bin/user/jsonengine.py',
             'bin/user/sunevents.py']),
           ('skins/Bootstrap/css',
            ['skins/Bootstrap/css/bootstrap.min.css',
             'skins/Bootstrap/css/bootstrap-icons.min.css',
             'skins/Bootstrap/css/live.css',
             'skins/Bootstrap/css/images.css']),
           ('skins/Bootstrap/css/fonts',
            ['skins/Bootstrap/css/fonts/bootstrap-icons.woff',
             'skins/Bootstrap/css/fonts/bootstrap-icons.woff2']),
           ('skins/Bootstrap/js',
            ['skins/Bootstrap/js/bootstrap.bundle.min.js',
            'skins/Bootstrap/js/charts.js',
            'skins/Bootstrap/js/echarts.min.js',
            'skins/Bootstrap/js/echarts_i18n/langDE.js',
            'skins/Bootstrap/js/echarts_i18n/langEN.js',
            'skins/Bootstrap/js/echarts_i18n/langES.js',
            'skins/Bootstrap/js/echarts_i18n/langFR.js',
            'skins/Bootstrap/js/echarts_i18n/langIT.js',
            'skins/Bootstrap/js/echarts_i18n/langNL.js',
            'skins/Bootstrap/js/echarts_i18n/langTH.js',
            'skins/Bootstrap/js/echarts_i18n/langZH.js',
             'skins/Bootstrap/js/jquery.min.js',
            'skins/Bootstrap/js/gauges.js',
            'skins/Bootstrap/js/mqtt.min.js',
            'skins/Bootstrap/js/luxon.min.js',
            'skins/Bootstrap/js/periodchartcore.js',
            'skins/Bootstrap/js/periodcharts.js',
            'skins/Bootstrap/js/periodcore.js',
            'skins/Bootstrap/js/periodpicker.js',
            'skins/Bootstrap/js/periods.js',
            'skins/Bootstrap/js/periodsdata.js',
            'skins/Bootstrap/js/periodstore.js',
            'skins/Bootstrap/js/site.js',
            'skins/Bootstrap/js/units.js',
            'skins/Bootstrap/js/windradarcore.js']),
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

        super(BootstrapInstaller, self).__init__(
            version= self._version,
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
        print("   https://www.weewx.com/docs/5.1/custom/localization/")

        print("")
        print("Default location for HTML files is public_html/Bootstrap")
        print("*** POINT YOUR BROWSER TO: public_html/Bootstrap/index.html ***")
        print("")
        print("Day/week/month/year charts are built from the archive by a background worker;")
        print("after an upgrade, old day.html/week.html/month.html/year.html and *.png files")
        print("in the report directory are no longer generated and can be deleted.")
        print("")
