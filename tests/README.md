# Tests

## Python (backend)

Requires Python 3 with `pytest`, `configobj` and `jsonschema` (plus `tzdata` on Windows) and a WeeWX 5 source tree:

```
git clone --depth 1 --branch v5.5.2 https://github.com/weewx/weewx.git /tmp/weewx
WEEWX_SRC=/tmp/weewx/src python -m pytest tests/python -q
```

## JavaScript (frontend logic)

Requires Node.js 18 or later; no packages needed:

```
node --test tests/js
```

## Manual acceptance (UI)

The browser UI is accepted manually. After installing the skin and running at least one report cycle:

Live (must be unchanged):
- [ ] Live gauges and charts render and update via MQTT as before.
- [ ] Live day/night background and chart tooltips behave as before.
- [ ] `weewxData.json` still contains all previous Live keys (new keys `period_charts`, `period_config`, `period_titles` are additive).
- [ ] Switching Live → Day/Week/Month/Year → Live restores the Live view without reload errors.
- [ ] No errors in the browser console.

Period views:
- [ ] Day/Week/Month/Year buttons and `#day`, `#week`, `#month`, `#year` deep links open the right view.
- [ ] Rolling view, Back/Forward navigation and the period picker work; unavailable periods are disabled.
- [ ] Charts show gaps for missing data, the status line shows backfill progress and load errors.
- [ ] Refresh intervals from `[PeriodCharts][[refresh]]` are honoured.

Other pages and languages:
- [ ] Statistics, history, news and about pages still render.
- [ ] A translated report (e.g. `lang = de`) shows translated labels and locale date formats.
