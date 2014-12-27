# installer for the bootstrap skin.
#
# Based on installer for xstats
#
# 27 March 2014
# Configured by Nick to install bootstrap skin.

from setup import ExtensionInstaller

def loader():
    return BootstrapInstaller()

class BootstrapInstaller(ExtensionInstaller):
    def __init__(self):
        super(BootstrapInstaller, self).__init__(
            version="2.1",
            name='bootstrap',
            description='A skin based around the bootstrap 3.2.0 framework',
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
                            'image_width' : '800',
                            'image_height' : '500'}},
                    'HTMLPages': {
                        'skin':'Bootstrap',
                        'HTML_ROOT':'Bootstrap'}}},

            files=[('skins/Bootstrap',
                    ['skins/Bootstrap/about.html.tmpl',
                     'skins/Bootstrap/history.html.tmpl',
                     'skins/Bootstrap/index.html.tmpl',
                     'skins/Bootstrap/month.html.tmpl',
                     'skins/Bootstrap/news.html.tmpl',
                     'skins/Bootstrap/stats.html.tmpl',
                     'skins/Bootstrap/week.html.tmpl',
                     'skins/Bootstrap/year.html.tmpl',
                     'skins/Bootstrap/skin.conf']),
                   ('skins/Bootstrap/NOAA',
                    ['skins/Bootstrap/NOAA/NOAA-YYYY.html.tmpl',
                     'skins/Bootstrap/NOAA/NOAA-YYYY-MM.txt.tmpl']),
                   ('skins/Images', 
                    ['skins/Images/skin.conf']),
                   ('bin/user',
                    ['bin/user/gaugeengine.py',
                     'bin/user/gauges.py',
                     'bin/user/historygenerator.py']),
                   ('public_html/Bootstrap/css',
                    ['public_html/Bootstrap/css/bootstrap.min.css']),
                   ('public_html/Bootstrap/js',
                    ['public_html/Bootstrap/js/bootstrap.min.js'])
                   ]
            )

