Theme for Weewx weather station software.
============
Gauge and Chart graphics showing current conditions.

English example             |  German example with combined line/bar chart and scatter chart
:-------------------------:|:-------------------------:
![image](https://github.com/brewster76/fuzzy-archer/assets/58649043/d3d948ff-763e-42cd-a653-e40f3e6fdacb)  |  ![image](https://github.com/brewster76/fuzzy-archer/assets/58649043/aefe0b81-742a-453a-9e1f-3859330cc414)

See it in action with live data (10s. refresh interval):

[Weather test page english](https://www.kainzbauer.net/weather/Rif/en)

[Wetter Testseite Deutsch](https://www.kainzbauer.net/weather/Rif/de)

Interactive charts showing conditions over a timespan


MQTT enabled Gauges and charts - live weather data! 
(Live data needs extra extensions and configurations for publishing and subscribing MQTT messages and topics) see: https://github.com/brewster76/fuzzy-archer/wiki/MQTT-setup

Statistics: daily/weekly/monthly/yearly/alltime, highs/lows, ...

Historic data in color coded html tables.

Available in multiple languages. Help wanted! We need help with translations for:

- traditional chinese
- czech
- spanish
- finnish (there isn't even a language file stub yet)
- french
- greek
- italian
- korean (there isn't even a language file stub yet)
- dutch
- thai

Read the upgrading guide, if you already have an older version installed: https://github.com/brewster76/fuzzy-archer/wiki/Upgrading-to-v4

New in v4.1:

- Mixed charts: you can now mix "line" series with "bar" series. A mixed radiation/UV chart is already in the configs, you can enable it by adding it to live_chart_items
- New chart type "scatter". A scatter chart for lightning strikes and distance is already in the configs, you can enable it by adding it to live_chart_items
- Configurable custom pages
- Configurable news items
- More config options for charts
- Gauges, charts, stats and history items are now shown and ordered explicitly using a configuration list.
- localization throughout charts and gauges (the stats and history page still depends on the systems locale, see https://github.com/weewx/weewx/issues/867)
- Bugfixes and enhancements

New in v4.0:

- Complete and thorough overhaul of the skin, many breaking changes. It is recommended to start over with a fresh install
- This skin used to consist of three skins, now reduced to one
- Localization is now done the WeeWX way
- Less and easier configuration
- Many customizations can now be done by configuration only, no more need to touch the templates
- Day/night background in Live Charts (needs pyephem installed)
- Bug fixes and other enhancements

![Example_Rif](https://kainzbauer.net/example_rif.png)

See it in action (legacy v2.x): [dajda.net](http://dajda.net/)

Gauge with 3 Needles / Markers examples:

![Example 1](https://github.com/danimaciasperea/fuzzy-archer/blob/master/curImpTempGauge.png)

![Example 2](https://github.com/danimaciasperea/fuzzy-archer/blob/master/inTempGauge.png)

Frequently asked questions: [here](https://github.com/brewster76/fuzzy-archer/issues?q=label%3AFAQ+)
