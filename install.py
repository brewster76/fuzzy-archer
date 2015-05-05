# installer for the bootstrap skin.
#
# Based on installer for xstats
#
# Configured by Nick to install bootstrap skin, 2014-2015.

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
        super(BootstrapInstaller, self).__init__(
            version="2.21",
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

            files=[('skins/Bootstrap',
                    ['skins/Bootstrap/about.html.tmpl',
                     'skins/Bootstrap/history.html.tmpl',
                     'skins/Bootstrap/index.html.tmpl',
                     'skins/Bootstrap/month.html.tmpl',
                     'skins/Bootstrap/news.html.tmpl',
                     'skins/Bootstrap/stats.html.tmpl',
                     'skins/Bootstrap/week.html.tmpl',
                     'skins/Bootstrap/year.html.tmpl',
                     'skins/Bootstrap/gauges.html.tmpl',
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
                     'bin/user/translategenerator.py']),
                   ('skins/Bootstrap/css',
                    ['skins/Bootstrap/css/bootstrap.min.css']),
                   ('skins/Bootstrap/js',
                    ['skins/Bootstrap/js/bootstrap.min.js',
                     'skins/Bootstrap/js/ekko-lightbox.min.js']),
                   ('skins/languages',
                    ['skins/languages/espanol.conf',
                      'skins/languages/francais.conf',
                      'skins/languages/italian.conf',
                      'skins/languages/german.conf'])
                   ]
            )

        print ""
        print "The following alternative languages are available:"
        self.language = None

        for f in self.files:
            if f[0] == 'skins/languages':
                for language in f[1]:
                    l = language.strip('conf').split('/')[-1]
                    print "   %s" % l[:-1]

        print ""
        print "Would you like to use one of these? (y/n)"
        
        try:
            choice = distutils.util.strtobool(raw_input().lower())
        except:
            pass
        else:
            if choice is 1:
                print "Which language?"
                self.language = raw_input().lower()

    def merge_config_options(self):
        """Sets the language in skins/Bootstrap/skin.conf and skins/Images/skin.conf"""

        super(BootstrapInstaller, self).merge_config_options()

        fn = os.path.join(self.layout['CONFIG_ROOT'], 'weewx.conf')
        config = configobj.ConfigObj(fn)
        skin_dir = setup.get_skin_dir(config)

        if self.language is None or len(self.language) is 0:
            pass

        else:
            self.log("Setting language to %s" % self.language, level=1)

            for conf_file in self._skin_conf_files:
                skin_file = os.path.join(skin_dir, conf_file)
                skin_dict = configobj.ConfigObj(skin_file)

                if 'Language' not in skin_dict:
                    skin_dict['Language'] = {}

                skin_dict['Language']['language'] = self.language
                skin_dict.write()


    def install(self):
        super(BootstrapInstaller, self).install()

        web_page_text = "HTML and image files will be stored here: %s" % \
              os.path.join(self.layout['CONFIG_ROOT'], self.config['StdReport']['HTMLPages']['HTML_ROOT'])

        wl = len(web_page_text)

        print ""
        print "+%s+" % ('-' * (wl + 2))
        print "| %s |" % web_page_text
        print "+%s+" % ('-' * (wl + 2))
        print ""