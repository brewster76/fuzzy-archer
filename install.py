# installer for the bootstrap skin.
#
# Based on installer for xstats
#
# Configured by Nick to install bootstrap skin, 2014-2022

import os.path
import configobj

import setup
import distutils

def loader():
    return BootstrapInstaller()

class BootstrapInstaller(setup.ExtensionInstaller):
    _skin_conf_files = ['Bootstrap/skin.conf',
                        'Images/skin.conf']

    def __init__(self):
        files=[('skins/Bootstrap',
            ['skins/Bootstrap/about.html.tmpl',
             'skins/Bootstrap/chartTemplate.html.inc',
             'skins/Bootstrap/day.html.tmpl',
             'skins/Bootstrap/foot.html.inc',
             'skins/Bootstrap/graphMenu.html.inc',
             'skins/Bootstrap/head.html.inc',
             'skins/Bootstrap/history.html.tmpl',
             'skins/Bootstrap/index.html.tmpl',
             'skins/Bootstrap/livegauges.html.inc',
             'skins/Bootstrap/month.html.tmpl',
             'skins/Bootstrap/nav.html.inc',
             'skins/Bootstrap/news.html.tmpl',
             'skins/Bootstrap/script.html.inc',
             'skins/Bootstrap/imagescript.html.inc',
             'skins/Bootstrap/stats.html.tmpl',
             'skins/Bootstrap/week.html.tmpl',
             'skins/Bootstrap/year.html.tmpl',
             'skins/Bootstrap/skin.conf']),
           ('skins/Bootstrap/NOAA',
            ['skins/Bootstrap/NOAA/NOAA-YYYY.txt.tmpl',
             'skins/Bootstrap/NOAA/NOAA-YYYY-MM.txt.tmpl']),
           ('skins/Images',
            ['skins/Images/skin.conf']),
           ('bin/user',
            ['bin/user/gaugeengine.py',
             'bin/user/gauges.py',
             'bin/user/historygenerator.py',
             'bin/user/jsonengine.py',
             'bin/user/sunevents.py',
             'bin/user/translategenerator.py']),
           ('skins/Bootstrap/css',
            ['skins/Bootstrap/css/bootstrap.min.css',
             'skins/Bootstrap/css/live.css']),
           ('skins/Bootstrap/js',
            ['skins/Bootstrap/js/bootstrap.bundle.min.js',
            'skins/Bootstrap/js/charts.js',
            'skins/Bootstrap/js/echarts.min.js',
             'skins/Bootstrap/js/jquery-3.6.3.min.js',
            'skins/Bootstrap/js/gauges.js',
            'skins/Bootstrap/js/lang.js',
            'skins/Bootstrap/js/mqtt.min.js',
            'skins/Bootstrap/js/site.js',
            'skins/Bootstrap/js/units.js']),
           ('skins/Bootstrap/lang',
            ['skins/Bootstrap/lang/cn.conf',
             'skins/Bootstrap/lang/cz.conf',
             'skins/Bootstrap/lang/de.conf',
             'skins/Bootstrap/lang/en.conf',
             'skins/Bootstrap/lang/es.conf',
             'skins/Bootstrap/lang/fr.conf',
             'skins/Bootstrap/lang/gr.conf',
             'skins/Bootstrap/lang/it.conf',
             'skins/Bootstrap/lang/nl.conf',
             'skins/Bootstrap/lang/no.conf',
             'skins/Bootstrap/lang/th.conf'])]

        super(BootstrapInstaller, self).__init__(
            version="3.1",
            name='bootstrap',
            description='A skin based around the bootstrap 5.2.0 framework',
            author="Nick Dajda",
            author_email="nick.dajda@gmail.com",
            config={
                'StdReport': {
                    'SmallImages': {
                        'skin':'Images',
                        'HTML_ROOT':'Bootstrap/images'},
                    'BigImages': {
                        'skin':'Images',
                        'HTML_ROOT':'Bootstrap/big_images',
                        'ImageGenerator' : {
                            'image_width'            : '900',
                            'image_height'           : '600',
                            'anti_alias'             : '2',
                            'top_label_font_size'    : '18',
                            'unit_label_font_size'   : '18',
                            'bottom_label_font_size' : '14',
                            'axis_label_font_size'   : '14'}},
                    'HTMLPages': {
                        'skin':'Bootstrap',
                        'HTML_ROOT':'Bootstrap'}}},
            files=files)

        print("")
        print("The following alternative languages are available:")
        self.language = None

        for f in files:
            if f[0] == 'skins/languages':
                for language in f[1]:
                    l = language.strip('conf').split('/')[-1]
                    print(("   %s" % l[:-1]))

        print("")
        print("Change to a different language using the [Language] setting in:")
        print("   Webpage text: skins/Bootstrap/skin.conf")
        print("   Images:       skins/Images/skin.conf")

        print("")
        print("Default location for HTML and image files is public_html/Bootstrap")
        print("*** POINT YOUR BROWSER TO: public_html/Bootstrap/index.html ***")
        print("")
