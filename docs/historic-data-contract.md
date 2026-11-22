# Period views: data contract (schema version 1)

This document is the binding contract between the backend (`bin/user/history*.py`) and the
frontend period views **Day / Week / Month / Year**. It does **not** apply to `Live!`:
`weewxData.json`, `ts.json`, `[LiveCharts]`, MQTT and the Live refresh stay unchanged
(only additive keys are added to `weewxData.json`, see §8).

Reference: WeeWX 5.5.2. Machine-readable schemas: `docs/schemas/*.schema.json`.

## 1. Time semantics

### 1.1 Units and time zone

* All timestamps in all files are **Unix epoch seconds (UTC), integers** (`"time_unit": "s"`).
  The frontend multiplies by 1000 for ECharts/Luxon.
* The station time zone is the **time zone of the WeeWX host process**. WeeWX itself computes all
  calendar spans (`archiveDaySpan`, `archiveWeekSpan`, daily summaries) in process local time,
  so the period views use the same zone. The IANA name is detected with `tzlocal`
  (as `jsonengine.py` already does). If no IANA name is available, a warning is logged, the
  backend still uses host local time and `timezone.name` is `null`; the frontend then falls back
  to the UTC offsets in `timezone.transitions`.
* Every file carries `timezone.transitions`: `[[epoch, utc_offset_seconds], ...]`, the first entry
  at (or before) `axis.start`, followed by every offset change inside the axis range. Ambiguous
  local times (DST fall-back) are therefore always identifiable via epoch + offset.

### 1.2 WeeWX record selection semantics

A WeeWX archive record with timestamp `ts` and `interval` (minutes) describes the interval
`(ts - interval*60, ts]`. WeeWX aggregates (`weewx.xtypes.ArchiveTable`) select
`dateTime > start AND dateTime <= stop`; daily summaries (`DailySummaries`) are built with the
same rule (`archiveDaySpan`: a record exactly at midnight belongs to the previous day).

**Every span in this contract is half-open on the left: `(start, end]`.** A record exactly at a
boundary belongs to the interval/period that *ends* at that boundary. No record is counted twice.

### 1.3 Calendar periods

| period | id format | span |
|---|---|---|
| `day` | `yyyyMMdd` | local midnight → next local midnight |
| `week` | `yyyyMMdd` = local **start** date | local 00:00 of the configured first weekday → same weekday next week |
| `month` | `yyyyMM` | local 00:00 on the 1st → 1st of next month |
| `year` | `yyyy` | local 00:00 on Jan 1st → Jan 1st of next year |

* First weekday = WeeWX `[Station] week_start` (`weewx.station.StationInfo.week_start`,
  0 = Monday … 6 = Sunday, default 6). Encoded in files and manifest as that integer. There is no
  separate skin option. ISO week numbers are never used.
* Boundaries are computed from local calendar dates, never by adding 86400/604800 seconds;
  23 h / 25 h days are normal.
* If local 00:00 does not exist on a date (DST gap at midnight), the period starts at the first
  existing local instant after the gap.
* A calendar period is *completed* when `now >= period end`. It is written to the immutable
  history by the first successful run after its end, from archive data (a running file is never
  renamed).

### 1.4 Rolling windows

`week` / `month` / `year` rolling windows: `window.end = generation time`,
`window.start = window.end - N * 86400` with N = 8 / 32 / 367. DST does not change the duration.
No rounding to midnight. Rolling windows are not aligned to `week_start`.

### 1.5 Aggregation grids

Resolution codes (string, used in config and files):

| code | local boundaries |
|---|---|
| `native` | none – archive records as stored (each point = one record) |
| `PT5M` | every local hh:00, :05, …, :55 |
| `PT10M` | every local hh:00, :10, …, :50 |
| `PT15M` | every local hh:00, :15, :30, :45 |
| `PT30M` | every local hh:00, :30 |
| `PT1H` | every full local hour |
| `PT2H` | local 00:00, 02:00, …, 22:00 |
| `PT3H` | local 00:00, 03:00, …, 21:00 |
| `PT6H` | local 00:00, 06:00, 12:00, 18:00 |
| `P1D` | local midnight → next local midnight (calendar day, *not* 86400 s) |

* Boundaries are local wall-clock times, independent of generation time, window start or first
  record. Non-existent local boundaries (spring-forward) are skipped; repeated local boundaries
  (fall-back) are both emitted and distinguished by epoch. Actual bucket durations can therefore
  differ from the nominal duration.
* `weeutil.weeutil.intervalgen` is **not** used: in 5.5.2 it merges the repeated hour on
  fall-back and starts at the given timestamp. The backend generates boundaries itself and calls
  `weewx.xtypes.get_aggregate(obs_type, TimeSpan(start, end), aggregate_type, db_manager)` for
  every bucket. For `P1D` buckets (midnight-aligned) WeeWX automatically uses the daily summaries.
* Edge buckets are never truncated: every bucket that intersects the axis range is computed
  over its full nominal span, even if part of it lies outside the window (example: window start
  10:07 with `PT15M` → first bucket `(10:00, 10:15]`). The frontend clips only the drawing.
* A bucket with `end > coverage.last` in a running file is *provisional* (flag `1`). It keeps its
  nominal bounds and contains only records available at generation time. No future values are
  generated.

### 1.6 Statistics

Period statistics are computed server-side with `get_aggregate` over **exactly** the period
(calendar) or the window (rolling), `(start, end]` – never over the extended edge buckets and
never from chart points.

## 2. Files and directory layout

All paths are relative to the **data root** = `<HTML_ROOT of the generating report>/historic_data/`.

```text
historic_data/
  manifest.json                    index, written by the backfill worker (mutable, plain JSON)
  manifest/day/yyyy.json           segment: all days of local year yyyy
  manifest/week/yyyy.json          segment: all weeks whose start date is in year yyyy
  manifest/month/yyyy.json         segment: all months of year yyyy
  manifest/year/all.json           segment: all years
  current.json                     references to mutable files, written by the report generator
  current/day.json.gz              running calendar day   (mutable)
  current/week.json.gz             running calendar week  (mutable)
  current/month.json.gz            running calendar month (mutable)
  current/year.json.gz             running calendar year  (mutable)
  rolling/week.json.gz             rolling 8 days          (mutable)
  rolling/month.json.gz            rolling 32 days         (mutable)
  rolling/year.json.gz             rolling 367 days        (mutable)
  day/yyyyMMdd.json.gz             completed periods (immutable)
  week/yyyyMMdd.json.gz
  month/yyyyMM.json.gz
  year/yyyy.json.gz
```

* **One file per period** containing all series and the sun events (decision E8). This replaces
  the `…_{obs_type}.json` layout of the original specification. File names consist only of
  validated period ids (`^\d{4}$`, `^\d{6}$`, `^\d{8}$`); series keys never appear in paths, so path
  traversal and name collisions cannot occur.
* Period files are gzip-compressed JSON (UTF-8). The frontend checks the gzip magic bytes
  `1f 8b`; if the web server already removed the encoding, the body is parsed as plain JSON.
* All writes are atomic: temporary file in the same directory → flush/fsync → `os.replace`.
  Order: data file → manifest segment → `manifest.json` (resp. `current.json`).
* `rev` everywhere = first 12 hex chars of the SHA-1 of the written (compressed) bytes. The
  frontend fetches `…?r=<rev>`; a regenerated file gets a new `rev`, which invalidates browser
  and HTTP caches.
* Worker state, retry counters and locks are **not** published. They live in
  `<WEEWX_ROOT>/<SQLITE_ROOT>/fuzzy_archer/<hash of absolute data root>/` (same base directory
  the skin already uses for the skyfield ephemeris), overridable with `[PeriodCharts] state_root`.

## 3. Period file (`period-v1.schema.json`)

Same structure for completed, current and rolling files.

```jsonc
{
  "schema_version": 1,
  "time_unit": "s",
  "kind": "calendar",               // "calendar" | "rolling"
  "period": "week",                 // day | week | month | year
  "period_id": "20261115",          // null for rolling
  "state": "complete",              // see 3.1
  "week_start": 6,                  // only for period == "week" (calendar and rolling)
  "timezone": {"name": "Europe/Berlin", "transitions": [[1763161200, 3600]]},
  "generated": 1763820000,
  "period_span": {"start": 1763161200, "end": 1763766000},   // calendar period or rolling window, (start, end]
  "axis": {"start": 1763161200, "end": 1763766000},          // visible x range (= period_span)
  "coverage": {                     // archive records inside (period_span.start, min(period_span.end, generated)]
    "first": 1763161500, "last": 1763766000,
    "records": 2016, "expected": 2016, "archive_interval": 300
  },
  "unit_system": 1,                 // WeeWX unit system of the database (1 US, 16 METRIC, 17 METRICWX)
  "observations": {
    "wx_binding/outTemp": {
      "data_binding": "wx_binding", "data_type": "outTemp",
      "unit": "degree_F", "group": "group_temperature",
      "count": 2016,
      "stats": {"min": [12.3, 1763190000], "max": [55.1, 1763230000], "avg": 33.4}
    }
  },
  "series": {
    "wx_binding/outTemp/avg/PT15M": {
      "observation": "wx_binding/outTemp",
      "aggregate_type": "avg",
      "resolution": "PT15M",
      "unit": "degree_F", "group": "group_temperature",
      "points": [[1763161200, 1763162100, 33.1], [1763162100, 1763163000, null]]
    }
  },
  "sun_events": [[1763161200, 1.0, "start"], [1763185000, 0.5, "rising"]],
  "errors": []
}
```

`coverage.first`/`last` are `null` if the span contains no record. `errors` is always empty in
published files (reserved for diagnostics).

### 3.1 `state`

| value | meaning | immutable? |
|---|---|---|
| `complete` | completed period, generated without technical error, no archive gaps | yes |
| `gaps` | completed period, generated without technical error, real archive gaps | yes |
| `running` | current calendar period or rolling window | no |

Technically failed generations are **never published** (state (c) of the specification exists
only in the worker state and as manifest status `error`). A series whose query failed makes the
whole period fail; it is never written as a gap.

`gaps` ⇔ the percentage of missing archive records is greater than `[PeriodCharts] gap_threshold`
(default `1`, valid range `0..100`), with
`expected = floor((min(end, generated) - start) / archive_interval)` and `archive_interval`
= most frequent record `interval` in the span, in seconds.
Changing `gap_threshold` does not update already-published completed periods; regenerate them with
`python -m user.historyregen --period all` to apply the new threshold to the full history.

### 3.2 Keys

* **Observation key** = `<data_binding>/<data_type>`.
* **Series key** = `<data_binding>/<data_type>/<aggregate_type>/<resolution>`; for `native`
  series `aggregate_type` is `none`. The key contains every parameter that affects the
  computation, so identical series used by several charts are stored once (decision E26:
  keys derive from `[PeriodCharts]`, not from the raw obs_type).
* Wind direction is aggregated vectorially: `data_type = wind`, `aggregate_type = vecdir`
  (WeeWX `ArchiveTable`/`DailySummaries` `vecdir` on observation `wind`), unit group
  `group_direction`.

### 3.3 Points

`[start, end, value]` or `[start, end, value, 1]`:

* `(start, end]` = nominal bucket span (aggregated series) or `(ts - interval*60, ts]` of the
  archive record (`native`). The point is located at `end`; bars span `start…end`.
* `value` = number in the database unit (`unit`) or `null` (no data). No `NaN`/`Infinity`.
* 4th element `1` = provisional bucket (`end > coverage.last` in a running file).
* Points are sorted by `start`; aggregated series contain every bucket intersecting `axis`
  (including empty ones), native series only existing records.

### 3.4 Units

Values are stored in the database unit system (what `get_aggregate` returns). `unit` / `group`
are WeeWX names. The frontend converts with `units.js`: target unit =
`weewxData.units.Groups[group]`, function `window[unit + "_To_" + target]`; equal units are
not converted.

### 3.5 Statistics

`observations.*.stats` contains the configured statistics (§6.2):
`min`/`max` as `[value, epoch]` (WeeWX `min`/`mintime`, `max`/`maxtime`), `avg`, `sum` as numbers
and `vecavg`/`vecdir` for wind. Missing → `null`. Span = `period_span`.
`stat_units` (optional) maps a statistic to `[unit, group]` when its unit differs from the
observation unit (e.g. `vecavg` = wind speed for the observation `wind` or `windDir`).
`vecavg`/`vecdir` of `windDir`/`windSpeed` are computed on the WeeWX observation `wind`.
`count` = number of non-null values of the observation in `period_span`.

### 3.6 Sun events

Only for `day` and `week` (calendar and rolling) when `show_daynight = true` and skyfield is
available; otherwise `[]` (a log note is written; missing backgrounds are not a technical error).

* Computed with `user.sunevents.SunEvents(axis.start, axis.end, lon, lat, elev, path, ephemeris)
  .get_transits(transition_angle)` for the station position and the actual axis range.
* `[epoch, darkening_extent, type]`, `darkening_extent` in `0…1` with the same formula as
  `jsonengine.get_day_night_events`, `type` ∈ `start, rising, setting, transit, antitransit, end`.
  The `start` event carries the sun altitude at `axis.start`, so the state at the left edge is
  explicit (no "day until the first event" error). Days without sunrise/sunset simply contain no
  rising/setting events.

## 4. `current.json` (`current-v1.schema.json`)

Written by the report generator after the mutable files.

```jsonc
{
  "schema_version": 1,
  "generated": 1763820000,
  "week_start": 6,
  "current": {
    "day":   {"period_id": "20261122", "file": "current/day.json.gz",   "rev": "…", "generated": 1763820000, "refresh": 300},
    "week":  {"period_id": "20261115", "file": "current/week.json.gz",  "rev": "…", "generated": 1763818200, "refresh": 3600},
    "month": {"period_id": "202611",   "file": "current/month.json.gz", "rev": "…", "generated": 1763812800, "refresh": 10800},
    "year":  {"period_id": "2026",     "file": "current/year.json.gz",  "rev": "…", "generated": 1763805600, "refresh": 21600}
  },
  "rolling": {
    "week":  {"file": "rolling/week.json.gz",  "rev": "…", "generated": 1763818200, "refresh": 3600},
    "month": {"file": "rolling/month.json.gz", "rev": "…", "generated": 1763812800, "refresh": 10800},
    "year":  {"file": "rolling/year.json.gz",  "rev": "…", "generated": 1763805600, "refresh": 21600}
  }
}
```

`refresh` (seconds) = configured generation interval; the browser uses it as poll interval.
For `day` with `refresh = 0` it is the archive interval. Due-ness is checked against
`generated`, not against the number of report runs.

## 5. Manifest (`manifest-v1.schema.json`)

Written only by the backfill/regeneration worker (single writer, under the worker lock).

### 5.1 Index `manifest.json`

```jsonc
{
  "schema_version": 1,
  "generated": 1763820000,
  "week_start": 6,
  "archive": {"first": 1420070700, "last": 1763820000},
  "backfill": {"state": "running", "done": 3120, "total": 4380, "updated": 1763820000},
  "segments": {
    "day":   {"2026": "rev", "2025": "rev"},
    "week":  {"2026": "rev"},
    "month": {"2026": "rev"},
    "year":  {"all": "rev"}
  }
}
```

`backfill.state` ∈ `idle | running | done | error`. The frontend reloads a segment only when its
`rev` changed.

### 5.2 Segment `manifest/<period>/<key>.json`

```jsonc
{
  "schema_version": 1,
  "period": "day",
  "segment": "2026",
  "entries": {
    "20261118": {"s": "ok",    "rev": "3f2a9c01b7de", "file": "day/20261118.json.gz"},
    "20261119": {"s": "gaps",  "rev": "…", "file": "day/20261119.json.gz", "missing": ["wx_binding/UV"]},
    "20261120": {"s": "error", "tries": 3},
    "20261121": {"s": "nodata"},
    "20261122": {"s": "pending"}
  }
}
```

| `s` | calendar | loadable |
|---|---|---|
| `ok` | available | yes |
| `gaps` | available (missing data shown as gaps) | yes |
| `pending` | in generation, disabled | no |
| `nodata` | no data, disabled | no |
| `error` | error marker, disabled; after `max_retries` only `historyregen` retries | no |
| `incompatible` | "regeneration required", disabled | no |

* Only `ok`/`gaps` carry `file` and `rev`. `missing` lists observation keys of the current
  configuration without data (or absent) in that period; a period is selectable if at least one
  observation needed by the view has data.
* Completed periods between `archive.first` and now without an entry are treated as `pending`;
  the worker writes explicit `nodata` entries (determined from the archive, not from missing
  files). The running period of each type is never listed (it is in `current.json`).
* `incompatible`: file `schema_version` ≠ current, or week files with `week_start` ≠ current
  `week_start`. The worker never overwrites these automatically; `historyregen` does.
  After a change of `week_start` all week entries are marked `incompatible` until regenerated;
  the manifest never mixes old and new week boundaries (old ids are removed on regeneration).
* Uploads (FTP/rsync) happen with the next report cycle. A `404` for a referenced file is
  treated as "temporarily unavailable" and retried with backoff.

## 6. Configuration `[PeriodCharts]`

New section; `[LiveCharts]` is untouched.

```ini
[PeriodCharts]
    period_chart_items = outTemp, barometer, rain, outHumidity, wind, windDir
    generate = true             # false: this report only displays data of another report
    generate_history = false    # bundled Bootstrap default: current day + rolling windows only
    data_url = historic_data    # URL of the data root relative to this report's pages (E22)
    show_daynight = true        # day/week only
    transition_angle = 8
    gap_threshold = 1           # tolerated missing archive records before status "gaps" (%; 0..100)
                                # Changing it requires: python -m user.historyregen --period all
    state_root =                # default <WEEWX_ROOT>/<SQLITE_ROOT>/fuzzy_archer
    max_retries = 3             # then manifest status "error"
    retry_backoff = 600         # seconds, doubled per try
    backfill_pause = 0.02       # seconds sleep after each period (load limiting)
    [[refresh]]                 # generation interval of current + rolling files, seconds
        day = 0                 # 0 = every report run
        week = 3600
        month = 10800
        year = 21600
    [[defaults]]                # view defaults
        line_aggregate_type = avg   # default aggregation for non-native line/scatter series
        [[[day]]]
            line = native
            bar = native
        [[[week]]]
            line = PT15M
            bar = PT1H
        [[[month]]]
            line = PT2H
            bar = P1D
        [[[year]]]
            line = P1D
            bar = P1D
    [[outTemp]]                     # chart id
        showEmpty = true              # optional; default false, keep this chart visible with no plotted data
        [[[outTemp]]]               # series id (unique inside the chart)
            # data_binding = wx_binding   # default: WeeWX default binding
            # obs_type = outTemp           # WeeWX observation type; defaults to series id
            # data_type = outTemp          # legacy alias for obs_type
            # plotType = line             # line | bar | scatter
            # aggregateType = avg         # explicit aggregation (required for non-native bars)
            # aggregateInterval = PT15M   # explicit resolution for all views
            # statistics = min, max, avg  # default: see 6.2
            showMaxMarkPoint = true
            showMinMarkPoint = true
            showAvgMarkLine = true
            lineColor = '#b44242'
            decimals = 1
            [[[[day]]]]                   # optional per-view override of
                aggregateInterval = PT5M  # aggregateType / aggregateInterval
            [[[[year]]]]
                show = false              # hide this series in the year chart only
```

The bundled Bootstrap `skin.conf` sets `generate_history = false` by default, and the generator also
defaults to `false` when the option is omitted from a custom configuration. Set it explicitly to
`true` to enable full historical generation.

With `generate_history = false`, each report run generates today's calendar day, starting at station
local midnight, and rolling week/month/year windows. Each rolling window is a fixed-length span ending
at the generation time: 8 days for week, 32 days for month, and 367 days for year. The report writes
the current-day and rolling files and updates `current.json`; it omits calendar week/month/year files
and does not start the automatic worker that builds completed historical periods or its manifest.
The period picker and previous/next/current/today controls are hidden. Links to past days resolve to
today, while links to calendar weeks, months, and years resolve to the corresponding rolling view.

This setting does not delete existing historical files. `historyregen` can still be run explicitly,
but automatic historical backfill stays disabled. When enabling history generation, the backfill
worker may take a long time on a large archive and use hundreds of megabytes of disk space; configure
`backfill_pause` to limit its load.

Display options (`seriesName`, `plotType`, `lineColor`, `lineWidth`, `decimals`, `yAxisIndex`,
`yAxisMin`, `symbol`, `symbolSize`, `interval`, `minInterval`, `maxInterval`, `splitNumber`,
`labelFontSize`, `showTooltipValueNone`, `dataReferences`, `showMaxMarkPoint`, `showMinMarkPoint`,
`showAvgMarkLine`) have the same meaning as in `[LiveCharts]`. The per-view `show` option defaults
to `true`; set it to `false` to omit a series from that period's chart. Hidden series are also
excluded from that view's generated data unless another visible series needs the same data.
Period charts are hidden when none of their visible series has a non-null data point in the selected
view. Set the chart-level `showEmpty = true` option to keep a chart visible even when it has no
plotted data; it defaults to `false`. This option belongs directly under the chart section
(`[[outTemp]]`), not under an individual series.
For aggregated views, the localized aggregation type is appended to the series label (for example,
`Outside temperature (Max)`); translations come from `[Texts]` in the selected language file.
`payload_key`, `convertFunction`
and MQTT options are Live-only and ignored. Min/max mark points and the avg mark line use the
server-side statistics (§3.5), not values derived from chart points. They are drawn only for series
whose values are comparable with the raw record extremes: not for `sum` or `vecdir` aggregations
and not for direction series. Instead the legend shows the period total (`Σ`, statistic `sum`) of
`sum` series and the vector mean direction (`Ø`, statistic `vecdir`) of direction series.
`plotType = scatter` does not require `dataReferences` (unlike Live); if given, they name series
ids of the same chart, and points whose referenced value at the same bucket end is `0`/`null` are
hidden.

### 6.1 Resolution / aggregation priority

1. series per-view option (`[[[[week]]]] aggregateInterval` / `aggregateType`)
2. series option (`aggregateInterval` / `aggregateType`)
3. view default (`[[defaults]][[[<view>]]] line|bar`; `line_aggregate_type` for line/scatter)
4. documented fallback: `native` for the day view.

* `aggregateInterval` accepts a resolution code or one of the equivalent seconds values
  (300, 600, 900, 1800, 3600, 7200, 10800, 21600; 86400 → `P1D`).
* A **bar** series with a non-native resolution and no `aggregateType` is a configuration error:
  logged, series skipped. The aggregation is never guessed from the plot type.
* Line/scatter series without `aggregateType` use `line_aggregate_type` (a documented,
  configurable view default).
* `native` ignores `aggregateType`.

### 6.2 Default statistics

`aggregateType = sum` → `sum, max`; `aggregateType = vecdir` → `vecavg, vecdir`; otherwise
`min, max, avg`; observations `windDir`/`wind` always default to `vecavg, vecdir`. Overridable
with `statistics`. Non-native `windDir` series without `aggregateType` use `vecdir` (data type
`wind`) instead of `line_aggregate_type`.

## 7. Locks and processes

* Worker lock: `<state dir>/worker.lock` created with `O_CREAT|O_EXCL`, containing pid, host and
  start time; refreshed after every period. A lock is stale if the pid no longer exists (same
  host) or it was not refreshed for 30 minutes. Backfill and `historyregen` share this lock; the
  report generator never waits for it.
* The report generator writes only `current.json`, `current/*` and `rolling/*`; the worker writes
  only the manifest and completed period files. No file has two writers.
* `python -m user.historyregen --period {day|week|month|year|all}… [--from D] [--to D]
  [--series KEY…] [--config weewx.conf] [--report NAME] [--dry-run]` regenerates completed periods
  overlapping the range (`D` = `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; default whole archive) under the
  worker lock (exit code 2 if busy). It removes week entries/files that are `incompatible` or not
  aligned with the current `week_start` within the range, resets `error` entries and retry counters
  of regenerated periods, and deletes `worker.json` and `generator.json` so that the worker re-checks
  the archive and the generator rewrites current/rolling files on the next report run. `--series`
  limits regeneration to periods whose published file lacks a matching series key of the current
  configuration (observation type, `binding/type` or full series key).

## 8. Additive keys in `weewxData.json`

Added by `jsonengine.py` (Live ignores them; on any error the three keys are omitted and the Live
data is written unchanged):

* `period_charts` – `{"order": [chart ids], "charts": {id: {<chart options>, "series": {id: …}}}}`.
  Each series carries its display options, resolved `data_type` (`obs_type`, legacy `data_type`, else
  series id), `label` (`seriesName`, else
  `[Labels][[Generic]]`, else data type), `obs_group`, `target_unit` and
  `views.<view>` = `{key, observation, data_binding, data_type, aggregate_type, resolution,
  statistics, obs_group, target_unit}` (`obs_group` of a `vecdir` view is `group_direction`).
* `period_config` – `data_url`, `generate`, `generate_history`, `week_start` (0 = Monday … 6 = Sunday),
  `refresh`, `archive_interval`, `show_daynight`, `view_resolutions`, `errors` (configuration
  errors of `[PeriodCharts]`).
* `period_titles` – `day`, `week`, `month`, `year` formats from `[Units][[TimeFormats]]`
  `period_title_*` (defaults `%x`, `%x`, `%B %Y`, `%Y`). `%x` is replaced server-side by the date
  pattern of the report locale (e.g. `%d.%m.%Y`); the frontend formats the remaining tokens
  `%d %e %m %y %Y %b %B %a %A %%` with `month_names`, `month_abbr`, `day_names`, `day_abbr`
  (localized, days Monday first). The week title is `<first day>–<last day>`, each formatted with
  `week`.

UI texts (tab labels, `Current`, `Today`, `rolling`, state messages) are `[Texts]` keys of the
language files rendered into `index.html`; languages without them fall back to the English key.

Frontend routing (`js/periodcore.js`, `js/periods.js`): URL hash `#day/yyyyMMdd`, `#week`
(rolling), `#week/yyyyMMdd`, `#month[/yyyyMM]`, `#year[/yyyy]`; Live = no hash. Invalid, misaligned
or future ids fall back to the rolling window (day: today) with `history.replaceState`. Each tab
remembers its selection while the page is open; in rolling mode "previous" opens the running
calendar period. Title token `%e` = day of month without padding.

Frontend data loading (`js/periodstore.js`, `js/periodsdata.js`): `current.json` and `manifest.json`
are fetched with `?t=<now>` (re-checked at most every 60 s, on tab activation, when the browser tab
becomes visible and on every poll); manifest segments and period files with `?r=<rev>`. Completed
files are kept in an in-memory LRU of 100 files (key = path + rev); current/rolling files are cached
separately and reloaded only on a new `rev`. Concurrent requests for the same URL are merged,
failures are never cached and retried with backoff 5 s · 2ⁿ (max. 10 min). Mutable views poll
shortly after `generated + refresh` (at least every 60 s); pending entries and a running backfill
poll with the view's `refresh` (day: `archive_interval`). A selected running period that has ended
keeps showing its last running version ("provisional") until the worker publishes the completed file.

Frontend charts (`js/periodchartcore.js`, `js/periodcharts.js`): one ECharts instance per chart of
`period_charts.order`. The x axis is exactly `axis` (edge buckets are clipped). Lines and scatter
points are placed at the bucket end; lines are interrupted where consecutive points do not touch
(archive gaps, `null` values). Bars are drawn from `start` to `end` of each bucket, so DST days and
calendar days keep their real width; provisional buckets are drawn lighter. The axis tooltip shows,
for the hovered time `t`, every series' bucket with `start < t ≤ end`, its interval bounds and
"provisional" for provisional values. Day/night backgrounds are drawn from `sun_events` (day/week
only). Values are converted with `units.js`; a missing conversion function keeps the database
unit and logs a console note. Legend selections are kept when the same view is refreshed.

Period picker (`js/periodpicker.js`): day = month grid of days, week = month grid whose rows are the
weeks starting on `week_start` (a week is listed in the month of its first day), month = 12 months
of a year, year = pages of 12 years. Cell states come from the manifest (§5): `ok`/`gaps` and the
running period are selectable (`gaps` is hatched), `pending` (label "History is being built" while
the backfill runs), `nodata`, `error`, `incompatible` and future periods are disabled with a title.
Navigation is limited to the range from the first archive period to the running period. Selecting a
period navigates to `#<view>/<id>`; for week/month/year this leaves the rolling window. The panel
closes on selection, Escape, an outside click or a route change; selection and Escape return focus to
the picker button.

## 9. Versioning

`schema_version` is incremented on any incompatible change. Files with another version are
reported as `incompatible` and require `python -m user.historyregen`.
