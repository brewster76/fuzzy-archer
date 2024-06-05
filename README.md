Theme for WeeWX weather station software.
============
Gauge and Chart graphics showing current conditions.

English example             |  German example with combined line/bar chart and scatter chart
:-------------------------:|:-------------------------:
![image](https://github.com/brewster76/fuzzy-archer/assets/58649043/d3d948ff-763e-42cd-a653-e40f3e6fdacb)  |  ![image](https://github.com/brewster76/fuzzy-archer/assets/58649043/aefe0b81-742a-453a-9e1f-3859330cc414)
![mobile_en](https://github.com/brewster76/fuzzy-archer/assets/58649043/2b445b5c-250b-47ff-b80d-53e9c73b52d8) | ![mobile_de](https://github.com/brewster76/fuzzy-archer/assets/58649043/60abda1b-27b0-43ad-bff2-56881455f8b9)


See it in action with live data (10s. refresh interval):

[Example page english](https://www.kainzbauer.net/weather/Rif/en)

[Example page Deutsch](https://www.kainzbauer.net/weather/Rif)

Interactive charts showing conditions over a timespan


MQTT enabled Gauges and charts - live weather data! 
(Live data needs extra extensions and configurations for publishing and subscribing MQTT messages and topics) see: https://github.com/brewster76/fuzzy-archer/wiki/MQTT-setup

Statistics: daily/weekly/monthly/yearly/alltime, highs/lows, ...

Historic data in color coded html tables.

Available in multiple languages. Help wanted! We need help with translations for:

- czech
- spanish
- finnish (there isn't even a language file stub yet)
- french
- greek
- italian
- korean (there isn't even a language file stub yet)
- dutch
- thai

Read the upgrading guides in the wiki, if you already have an older version installed: https://github.com/brewster76/fuzzy-archer/wiki

New in v4.3:

- Upgraded dependencies
- WeeWX 5.1 and above supports configuration of an individual locale for each report
- Fixed issues
  - https://github.com/brewster76/fuzzy-archer/issues/137
  - https://github.com/brewster76/fuzzy-archer/issues/140
  - https://github.com/brewster76/fuzzy-archer/issues/141
  - https://github.com/brewster76/fuzzy-archer/issues/143
  - https://github.com/brewster76/fuzzy-archer/issues/144
  - https://github.com/brewster76/fuzzy-archer/issues/137
- New norwegian translation (thx to @[Aslak Vaa](https://github.com/aslak47))
- Added feature to configure gauge needle behaviour with null or missing data (thx to @[claudobahn](https://github.com/claudobahn))
- New default symbol for shipped lightning chart.
- symbolSize is configurable, even with a JS function (see shipped lightning chart configs)
- Other smaller fixes

Change list: https://github.com/brewster76/fuzzy-archer/compare/v4.2...4.3

New in v4.2:

- Upgraded dependencies
- Overhaul of the UI, optimizations for mobile devices, more compact on mobile devices
- Navbar is fixed on top, faster and easier navigation especially on mobile devices
- Introduced Bootstrap Icons (https://icons.getbootstrap.com/)
- History: redundant specification of maxvalues for colors was removed, remove them from your custom configs (leaving them will still work, but is of no use)
- Support for customizing report data JSON in front end
- Fixed async refresh for sum aggregation in live charts
- Config option for axis intervals
- Config option for station info items
- Moon phase, sunrise/set, rain summaries, uptime is now updated asyncronously every archive_interval
- Added rain summaries in station info

New in v4.1:

- Mixed charts: you can now mix "line" series with "bar" series. A mixed radiation/UV chart is already in the configs, you can enable it by adding it to live_chart_items
- New chart type "scatter". A scatter chart for lightning strikes and distance is already in the configs, you can enable it by adding it to live_chart_items
- Configurable custom pages
- Configurable news items
- More config options for charts
- Gauges, charts, stats and history items are now shown and ordered explicitly using a configuration list.
- Mulit-language linking support: you can switch languages vie dropdown in multi-language installations
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
