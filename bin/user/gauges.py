#
# Copyright (c) 2014 Nick Dajda <nick.dajda@gmail.com>
#
# Distributed under the terms of the GNU GENERAL PUBLIC LICENSE
#
"""Python gauge for PIL

    Typical usage:
        im = Images.new(dimensions, colours, ...)
        gauge = gaugeDraw(im, min, max, % of dial) <-- extends ImageDraw
        gauge.add_dial_labels(dictionary) <-- e.g. {0: 'N', 90: 'E', 180: 'S', 270: 'W'}
        gauge.add_needle(value)
        gauge.add_history(list, num_buckets)
        gauge.add_dial(minor_tick, major_tick, show_major_values)
        gauge.add_text( ("27", "degC", "(very hot)") )
        gauge.render()
        im.save("filename for png file")
"""

import math

import Image
import ImageDraw
import ImageFont

DEFAULT_FONT = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"

class GaugeDraw(ImageDraw.ImageDraw):
    """Class for rendering nice gauge images, e.g. for use on a weather station website."""

    def __init__(self, im, min, max, dial_range=270, background_colour=None):
        """Initialises the dial. 
           min = minimum value on dial
           max = maximum value on dial
           dial_range = any value between 0 and 360.
                        360: dial is a complete circle
                        180: dial is a semicircle
                        90: dial is a quarter of a complete circle"""
        # This class extends ImageDraw... Initialise it
        ImageDraw.ImageDraw.__init__(self, im)

        self.min_value = float(min)
        self.max_value = float(max)

        if dial_range < 360:
            self.min_angle = (360 - dial_range) / 2
            self.max_angle = 360 - self.min_angle
        else:
            self.min_angle = 0
            self.max_angle = 360
        
        # Derive image dimensions from im
        (self.image_width, self.image_height) = im.size
        self.gauge_origin = (int(self.image_width / 2), int(self.image_height / 2))

        if self.image_width < self.image_height:
            self.radius = self.image_width * 0.45
        else:
            self.radius = self.image_height * 0.45
    
        # If None, means no histogram data added
        self.num_buckets = None
        
        # Whether to draw the dial
        self.draw_dial = False

        # No value set
        self.gauge_value = None

        # Text caption will be stored here
        self.text_labels = None

        # Dial labels
        self.dial_labels = None

        # Default colours...
        self.colours = { 'histogram' : 4342452,
                         'background': 16777215,
                         'label'     : 0,
                         'dial_label': 0,
                         'dial'      : 7368816,
                         'needle'    : 11829826,
                         'text'      : 11829826}

        if background_colour is not None:
            self.colours['background'] = background_colour

        self.fillColorTuple = int2rgb(self.colours['histogram'])
        self.backColorTuple = int2rgb(self.colours['background'])

    def add_needle(self, value, needle_colour=None):
        """Draws a needle pointing towards value.

        needle_colour overrides the default"""
        self.gauge_value = value

        if needle_colour is not None:
            self.colours['needle'] = needle_colour

    def add_dial_labels(self, dial_labels = [], dial_label_font_size=12, dial_label_colour=None,
                        dial_label_font=None):
        """Takes a dictionary and draws text at every key.
        On a dial from 0 to 360, this dictionary would print the points of the compoass:
        {0: 'N', 90: 'E', 180: 'S', 270: 'W'}"""
        if type(dial_labels) is dict:
            self.dial_labels = dial_labels

        if dial_label_font is None:
            dial_label_font = DEFAULT_FONT

        self.dial_label_font = ImageFont.truetype(dial_label_font, dial_label_font_size)

        if dial_label_colour is not None:
            self.colours['dial_label'] = dial_label_colour

    def add_text(self, text_list = None, text_font_size=20,
                text_font=None, text_colour=None):
        """Adds multiple lines of text as a caption.
        Usually used to display the value of the gauge.

        If label_list is not set, will create a single line label based on the value the needle is pointing to
        (only works if add_needle function has already been called)."""

        if text_list is None:
            if self.gauge_value is None:
                # Not enough information to do anything useful
                return
            else:
                text_list = str(self.gauge_value)

        self.text_labels = []

        if type(text_list) is tuple:
            for l in text_list:
                self.text_labels.append(l)
        else:
                self.text_labels.append(text_list)

        if text_font is None:
            text_font = DEFAULT_FONT

        self.text_font = ImageFont.truetype(text_font, text_font_size)
        self.text_font_size = text_font_size

        if text_colour is not None:
            self.colours['text'] = text_colour

    def add_dial(self, major_ticks, minor_ticks=None, dial_format="%.1f", dial_font_size=12,
                dial_font=None, dial_colour=None, dial_label_colour=None):
        """Configures the background dial
        major_ticks and minor_ticks are how often to add a tick mark to the dial.

        Set dial_format to None to stop labelling every major tick mark"""

        try:
            self.major_tick = float(major_ticks)
        except:
            raise Exception("Need to specify a number for major_ticks.")
    
        self.minor_tick = minor_ticks
        self.dial_format = dial_format

        if dial_font is None:
            dial_font = DEFAULT_FONT

        self.dial_font = ImageFont.truetype(dial_font, dial_font_size)

        if dial_colour is not None:
            self.colours['dial'] = dial_colour

        if dial_label_colour is not None:
            self.colours['dial_label'] = dial_label_colour

        self.draw_dial = True

    def add_history(self, list, num_buckets, histogram_color=None):
        """Turn list of values into a histogram"""
        if num_buckets is None:
            raise Exception("Need to specify number of buckets to split histogram into.")
    
        self.num_buckets = num_buckets
    
        if list is None:
            raise Exception("No data specified.")
        
        self.buckets = [0.0] * num_buckets
        bucket_span = (self.max_value - self.min_value) / num_buckets
        num_points = 0
        roof = 0.0

        for data in list:
            # Ignore data which is outside range of gauge
            if (data < self.max_value) and (data > self.min_value):
                bucket = int((data - self.min_value) / bucket_span)

                if bucket >= num_buckets:
                    raise Exeption("Value %f gives bucket higher than num_buckets (%d)" % (data, num_buckets))
                else:
                    self.buckets[bucket] += 1.0
                    num_points += 1

                    if self.buckets[bucket] > roof:
                        roof = self.buckets[bucket]

        self.buckets = [i / roof for i in self.buckets]

        if histogram_color is not None:
            self.colours['histogram'] = histogram_color

    def render_simple_gauge(self, value=None, major_ticks=None, minor_ticks=None, label=None, font=None):
        """Helper function to create gauges with minimal code, eg:

        im = Image.new("RGB", (200, 200), (255, 255, 255)
        g = gauges.GaugeDraw(im, 0, 100)
        g.render_simple_gauge(value=25, major_ticks=10, minor_ticks=2, label="25")
        im.save("simple_gauge_image.png", "PNG")

        Does not support dial labels, histogram dial background or setting colours..
        """
        if value is not None:
            self.add_needle(value)

        if major_ticks is not None:
            self.add_dial(major_ticks, minor_ticks, dial_font=font)

        if label is not None:
            self.add_text(text_list=label, text_font=font)

        self.render()


    def render(self):
        """Renders the gauge. Call this function last."""

        if self.num_buckets is not None:
            angle = float(self.min_angle)
            angleStep = (self.max_angle - self.min_angle) / float(self.num_buckets)

            for bucket in self.buckets:
                fillColor = (self._calcColor(bucket, 0), self._calcColor(bucket, 1), self._calcColor(bucket, 2))

                self.pieslice((int(self.gauge_origin[0] - self.radius), int(self.gauge_origin[1] - self.radius),
                              int(self.gauge_origin[0] + self.radius), int(self.gauge_origin[1] + self.radius)),
                              int(angle + 90), int(angle + angleStep + 90), fill=fillColor)
                angle += angleStep

        if self.draw_dial is True:
            # Major tic marks and scale labels
            label_value = self.min_value

            for angle in self._frange(math.radians(self.min_angle), math.radians(self.max_angle),
                                      int(1 + (self.max_value - self.min_value) / self.major_tick)):

                startPoint = (self.gauge_origin[0] - self.radius * math.sin(angle)
                              * 0.93, self.gauge_origin[1] + self.radius * math.cos(angle) * 0.93)

                endPoint = (self.gauge_origin[0] - self.radius * math.sin(angle),
                            self.gauge_origin[1] + self.radius * math.cos(angle))

                self.line((startPoint, endPoint), fill=self.colours['dial'])

                if self.dial_format is not None:
                    text = str(self.dial_format % label_value)
                    string_size = self.dial_font.getsize(text)

                    label_point = (self.gauge_origin[0] - self.radius * math.sin(angle) * 0.80,
                                   self.gauge_origin[1] + self.radius * math.cos(angle) * 0.80)

                    label_point = (label_point[0] - string_size[0] / 2, label_point[1] - string_size[1] / 2)

                    self.text(label_point, text, font=self.dial_font, fill=self.colours['label'])

                    label_value += self.major_tick

            # Minor tic marks
            for angle in self._frange(math.radians(self.min_angle), math.radians(self.max_angle),
                                      int(1 + (self.max_value - self.min_value) / self.minor_tick)):

                startPoint = (self.gauge_origin[0] - self.radius * math.sin(angle)
                              * 0.97, self.gauge_origin[1] + self.radius * math.cos(angle) * 0.97)

                endPoint = (self.gauge_origin[0] - self.radius * math.sin(angle),
                            self.gauge_origin[1] + self.radius * math.cos(angle))

                self.line((startPoint, endPoint), fill=self.colours['dial'])

            # The edge of the dial
            self.arc((self.gauge_origin[0] - int(self.radius), self.gauge_origin[1] - int(self.radius),
                      self.gauge_origin[0] + int(self.radius), self.gauge_origin[1] + int(self.radius)),
                          self.min_angle + 90, self.max_angle + 90, self.colours['dial'])

            # Custom gauge labels?
            if self.dial_labels is not None:
                for k in self.dial_labels.keys():
                    angle = (k - self.min_value) / (self.max_value - self.min_value)
                    if (angle >= 0.0) and (angle <= 1):
                        angle = math.radians(self.min_angle + angle * (self.max_angle - self.min_angle))

                        string_size = self.dial_label_font.getsize(self.dial_labels[k])

                        label_point = (self.gauge_origin[0] - self.radius * math.sin(angle) * 0.80,
                                       self.gauge_origin[1] + self.radius * math.cos(angle) * 0.80)

                        label_point = (label_point[0] - string_size[0] / 2, label_point[1] - string_size[1] / 2)

                        self.text(label_point, self.dial_labels[k], font=self.dial_label_font,
                                  fill=self.colours['dial_label'])

        if self.text_labels is not None:
            vstep = self.text_font_size * 1.5
            vpos = self.gauge_origin[1] + self.radius * 0.42 - (vstep * len(self.text_labels)) / 2

            for l in self.text_labels:
                text = unicode(l.encode("utf-8"), 'utf8')
                textsize = self.text_font.getsize(text)

                self.text((self.gauge_origin[0] - (textsize[0] / 2), vpos), text,
                          font=self.text_font, fill=self.colours['text'])
                vpos += vstep

        # Do last - the needle is on top of everything
        if self.gauge_value is not None:
            angle = math.radians(self.min_angle + (self.gauge_value - self.min_value) *
                                 (self.max_angle - self.min_angle) / (self.max_value - self.min_value))

            endPoint = (self.gauge_origin[0] - self.radius * math.sin(angle) * 0.7, self.gauge_origin[1] + self.radius * math.cos(angle) * 0.7)
            leftPoint = (self.gauge_origin[0] - self.radius * math.sin(angle - math.pi * 7 / 8) * 0.2,
                         self.gauge_origin[1] + self.radius * math.cos(angle - math.pi * 7 / 8) * 0.2)
            rightPoint = (self.gauge_origin[0] - self.radius * math.sin(angle + math.pi * 7 / 8) * 0.2,
                          self.gauge_origin[1] + self.radius * math.cos(angle + math.pi * 7 / 8) * 0.2)
            midPoint = (self.gauge_origin[0] - self.radius * math.sin(angle + math.pi) * 0.1,
                        self.gauge_origin[1] + self.radius * math.cos(angle + math.pi) * 0.1)

            self.line((leftPoint, endPoint), fill=self.colours['needle'])
            self.line((rightPoint, endPoint), fill=self.colours['needle'])
            self.line((leftPoint, midPoint), fill=self.colours['needle'])
            self.line((rightPoint, midPoint), fill=self.colours['needle'])

    def _frange(self, start, stop, n):
        """Range function, for floating point numbers"""
        L = [0.0] * n
        nm1 = n - 1
        nm1inv = 1.0 / nm1
        for i in range(n):
            L[i] = nm1inv * (start * (nm1 - i) + stop * i)
        return L

    def _calcColor(self, value, index):
        diff = self.fillColorTuple[index] - self.backColorTuple[index]
        newColor = self.backColorTuple[index] + int(diff * value)

        if newColor < 0:
            newColor = 0

        if newColor > 0xff:
            newColor = 0xff

        return newColor

def int2rgb(x):
#
# Stolen from genploy.py Weewx file
#
    b = (x >> 16) & 0xff
    g = (x >> 8) & 0xff
    r = x & 0xff
    return r,g,b
