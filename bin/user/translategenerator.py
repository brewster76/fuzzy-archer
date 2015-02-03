#
# Copyright (c) 2015  Nick Dajda <nick.dajda@gmail.com>
#
# Distributed under the terms of the GNU GENERAL PUBLIC LICENSE
#
"""Provides a way of easily overriding labels in skin.conf files with other languages.
Useful for skin designers who want to use multiple skin.conf files and easily make
the skins available in multiple languages.

1) Place this file in bin/user/translategenerator.py

2) Store each language specific file in skins/languages/[language].conf
   Take a look at an existing one to see how they work.

3) Add this section to each skin.conf:
[Language]

    #
    # Set a language below and labels will be overridden with any that are specified in
    # skins/languages/[language].conf
    #

    language = espanol

4) Replace any instances of CheetahGenerator or ImageGenerator in skin.conf with
these translation classes:

[Generators]
        # Change from this:
        # generator_list = weewx.cheetahgenerator.CheetahGenerator, weewx.imagegenerator.ImageGenerator, weewx.reportengine.CopyGenerator

        # To this:
        generator_list = user.translategenerator.CheetahGeneratorTranslated, user.translategenerator.ImageGeneratorTranslated, weewx.reportengine.CopyGenerator
"""

import syslog
import os.path
from configobj import ConfigObj

from weewx.imagegenerator import ImageGenerator
from weewx.cheetahgenerator import CheetahGenerator

class ImageGeneratorTranslated(ImageGenerator):
    """Overwrite skin.conf dictionary with language specific entries"""

    def setup(self):
        language_dict = _get_language_dict(self.skin_dict, self.config_dict)

        if language_dict is not None:
            self.skin_dict.merge(language_dict)

        ImageGenerator.setup(self)


class CheetahGeneratorTranslated(CheetahGenerator):
    """Overwrite skin.conf dictionary with language specific entries"""

    def setup(self):
        language_dict = _get_language_dict(self.skin_dict, self.config_dict)

        if language_dict is not None:
            self.skin_dict.merge(language_dict)

        CheetahGenerator.setup(self)

def _get_language_dict(skin_dict, config_dict):
    """Look for this section in the skin.conf dictionary:
     [Language]
        language = espanol

    Returns None if not found, or a link to the corresponding language.conf
    dictionary."""

    language_dict = None

    if 'Language' in skin_dict:
        if 'language' in skin_dict['Language']:
            language = skin_dict['Language']['language']

            syslog.syslog(syslog.LOG_INFO, "%s: Language is %s" % (os.path.basename(__file__), language))

            # Figure out where the language config files can be found
            language_config_path = os.path.join(config_dict['WEEWX_ROOT'], config_dict['StdReport']['SKIN_ROOT'],
                                                'languages', "%s.conf" % language)

            try:
                language_dict = ConfigObj(language_config_path)
            except:
                syslog.syslog(syslog.LOG_INFO, "%s: Could not import lanuguage dictionary %s" %
                              os.path.basename(__file__), language_config_path)

                language_dict = None

    if language_dict is None:
        syslog.syslog(syslog.LOG_DEBUG, "%s: No language override specified." % (os.path.basename(__file__)))

    return language_dict