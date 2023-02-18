# -*- coding: utf-8 -*-
#    See the file LICENSE.txt for your rights.
#    Author: Michael Kainzbauer (github: mkainzbauer)
""" generates configs for large images from [ImageGenerator] section in skin.conf
#
"""
import time
import logging
import os.path
import weewx.reportengine
import copy

log = logging.getLogger(__name__)

large = "large-"
large_image_height_key = "large_image_height"
large_image_width_key = "large_image_width"
image_generator_key = 'ImageGenerator'


class LargeImageGenerator(weewx.reportengine.ReportGenerator):

    def run(self):
        start_time = time.time()
        try:
            image_generator_config = self.skin_dict[image_generator_key]

            large_image_width = 900
            try:
                large_image_width = self.skin_dict[image_generator_key][large_image_width_key]
            except KeyError:
                log.debug("using default value for large_image_width")

            large_image_height = 600
            try:
                large_image_height = self.skin_dict[image_generator_key][large_image_height_key]
            except KeyError:
                log.debug("using default value for large_image_height")

            self.generate_large_image_configs(image_generator_config, large_image_width, large_image_height)
            log.debug("[ImageGenerator]: %s" % image_generator_config)
        except KeyError:
            log.warning("LargeImageGenerator failed to read config or config missing")

        log.debug("%s: Generated large images configs in %.2f seconds" %
                 (os.path.basename(__file__), time.time() - start_time))

    def generate_large_image_configs(self, image_generator_config, large_image_width, large_image_height):
        for key, image_generator_config_item in image_generator_config.items():
            log.debug("key: %s" % key)
            log.debug("item: %s" % image_generator_config_item)
            if isinstance(image_generator_config_item, dict):
                image_generator_config[large + key] = self.add_image_group(image_generator_config_item,
                                                                           large_image_width, large_image_height)

    def add_image_group(self, image_group, large_image_width, large_image_height):
        new_image_group = {}
        for key, image_group_item in image_group.items():
            if isinstance(image_group_item, dict):
                new_image_group[large + key] = self.add_image(image_group_item)
            else:
                new_image_group[key] = image_group_item
        new_image_group['image_width'] = large_image_width
        new_image_group['image_height'] = large_image_height
        return new_image_group

    def add_image(self, image):
        new_image = {}
        for key, image_item in image.items():
            if isinstance(image_item, dict):
                new_image[key] = copy.copy(image_item)
            else:
                if not (key == 'image_width' or key == 'image_height'):
                    new_image[key] = image_item
        return new_image
