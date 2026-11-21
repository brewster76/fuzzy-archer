/*
 * Pure logic of the period views Day / Week / Month / Year (no DOM access).
 * Contract: docs/historic-data-contract.md. Usable in the browser (global `PeriodCore`, needs the
 * global `luxon`) and in node:test (module.exports, luxon passed to `create`).
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory;
    } else {
        root.PeriodCore = factory(root.luxon);
    }
}(typeof self !== "undefined" ? self : this, function (luxon) {
    "use strict";
    const DateTime = luxon.DateTime;

    const VIEWS = ["live", "day", "week", "month", "year"];
    const PERIOD_VIEWS = ["day", "week", "month", "year"];
    const ROLLING_VIEWS = ["week", "month", "year"];
    const ROLLING_DAYS = {week: 8, month: 32, year: 367};
    const ID_PATTERN = {day: /^\d{8}$/, week: /^\d{8}$/, month: /^\d{6}$/, year: /^\d{4}$/};
    const UNIT = {day: "days", week: "weeks", month: "months", year: "years"};

    /** Luxon zone for weewxData.config.station_timezone (IANA name or "+HH:mm"). */
    function zoneName(stationTimezone) {
        if (stationTimezone === undefined || stationTimezone === null || stationTimezone === "" || stationTimezone === "local") {
            return "local";
        }
        if (/^[+-]\d{1,2}(:\d{2})?$/.test(stationTimezone)) {
            return "UTC" + stationTimezone;
        }
        return stationTimezone;
    }

    function isPeriodView(view) {
        return PERIOD_VIEWS.indexOf(view) >= 0;
    }

    function hasRolling(view) {
        return ROLLING_VIEWS.indexOf(view) >= 0;
    }

    /** Start of the calendar period with id `id` (local 00:00, first instant after a DST gap). */
    function periodStart(view, id, zone) {
        if (!isValidIdFormat(view, id)) {
            return null;
        }
        let year = Number(id.substring(0, 4));
        let month = id.length >= 6 ? Number(id.substring(4, 6)) : 1;
        let day = id.length >= 8 ? Number(id.substring(6, 8)) : 1;
        let dt = DateTime.fromObject({year: year, month: month, day: day}, {zone: zone});
        if (!dt.isValid || dt.year !== year || dt.month !== month || dt.day !== day) {
            return null;
        }
        return dt.startOf("day");
    }

    function periodEnd(view, id, zone) {
        let start = periodStart(view, id, zone);
        return start === null ? null : start.plus({[UNIT[view]]: 1}).startOf("day");
    }

    function isValidIdFormat(view, id) {
        return typeof id === "string" && ID_PATTERN[view] !== undefined && ID_PATTERN[view].test(id);
    }

    /** Valid period id; week ids must start on the configured first weekday (0 = Monday … 6 = Sunday). */
    function isValidId(view, id, zone, weekStart) {
        let start = periodStart(view, id, zone);
        if (start === null) {
            return false;
        }
        if (view === "week") {
            return start.weekday === Number(weekStart) + 1;
        }
        return true;
    }

    function formatId(view, dt) {
        if (view === "year") {
            return dt.toFormat("yyyy");
        }
        if (view === "month") {
            return dt.toFormat("yyyyMM");
        }
        return dt.toFormat("yyyyMMdd");
    }

    /** Id of the calendar period containing epoch milliseconds `ms`, `(start, end]` semantics are
     *  irrelevant here: an instant belongs to the period whose local date contains it. */
    function periodIdAt(view, ms, zone, weekStart) {
        let dt = DateTime.fromMillis(ms, {zone: zone});
        if (view === "week") {
            let offset = (dt.weekday - (Number(weekStart) + 1) + 7) % 7;
            dt = dt.minus({days: offset});
        }
        return formatId(view, dt);
    }

    /** Calendar-adjacent period id (`delta` periods later/earlier). */
    function shiftId(view, id, delta, zone) {
        let start = periodStart(view, id, zone);
        if (start === null) {
            return null;
        }
        return formatId(view, start.plus({[UNIT[view]]: delta}));
    }

    function compareIds(a, b) {
        return a < b ? -1 : (a > b ? 1 : 0);
    }

    /**
     * Next selectable period in direction `step` (+1/-1) starting at `id`, skipping periods for which
     * `isSelectable(id)` is false, never beyond `currentId` (running period) or before `firstId`.
     * Returns null at the boundaries.
     */
    function neighbourId(view, id, step, zone, currentId, firstId, isSelectable, maxSteps) {
        let limit = maxSteps === undefined ? 4000 : maxSteps;
        let candidate = id;
        for (let i = 0; i < limit; i++) {
            candidate = shiftId(view, candidate, step, zone);
            if (candidate === null) {
                return null;
            }
            if (currentId !== undefined && currentId !== null && compareIds(candidate, currentId) > 0) {
                return null;
            }
            if (firstId !== undefined && firstId !== null && compareIds(candidate, firstId) < 0) {
                return null;
            }
            if (isSelectable === undefined || isSelectable(candidate)) {
                return candidate;
            }
        }
        return null;
    }

    /** Parses "#week/20261115" → {view: "week", id: "20261115"}; "#week" → rolling (id null). */
    function parseHash(hash) {
        let value = (hash || "").replace(/^#/, "");
        try {
            value = decodeURIComponent(value);
        } catch (e) {
            // keep raw value
        }
        if (value === "" || value === "live") {
            return {view: "live", id: null};
        }
        let parts = value.split("/");
        let view = parts[0];
        if (!isPeriodView(view) || parts.length > 2) {
            return null;
        }
        let id = parts.length === 2 && parts[1] !== "" ? parts[1] : null;
        if (id !== null && !isValidIdFormat(view, id)) {
            return null;
        }
        return {view: view, id: id};
    }

    function formatHash(view, id) {
        if (view === "live") {
            return "";
        }
        return "#" + view + (id ? "/" + id : "");
    }

    function pad(value, width, character) {
        let s = String(value);
        while (s.length < width) {
            s = character + s;
        }
        return s;
    }

    /** strftime subset `%d %e %m %y %Y %b %B %a %A %%` with localized names from period_titles. */
    function formatDate(fmt, dt, titles) {
        titles = titles || {};
        let names = function (key, index, fallback) {
            let list = titles[key];
            return Array.isArray(list) && list[index] !== undefined ? list[index] : fallback;
        };
        return String(fmt).replace(/%([deymYbBaA%])/g, function (match, token) {
            switch (token) {
                case "d": return pad(dt.day, 2, "0");
                case "e": return String(dt.day);
                case "m": return pad(dt.month, 2, "0");
                case "y": return pad(dt.year % 100, 2, "0");
                case "Y": return String(dt.year);
                case "b": return names("month_abbr", dt.month - 1, dt.toFormat("LLL"));
                case "B": return names("month_names", dt.month - 1, dt.toFormat("LLLL"));
                case "a": return names("day_abbr", dt.weekday - 1, dt.toFormat("ccc"));
                case "A": return names("day_names", dt.weekday - 1, dt.toFormat("cccc"));
                case "%": return "%";
            }
            return match;
        });
    }

    const DEFAULT_TITLES = {day: "%d.%m.%Y", week: "%d.%m.%Y", month: "%B %Y", year: "%Y"};

    function titleFormat(titles, view) {
        return titles && titles[view] ? titles[view] : DEFAULT_TITLES[view];
    }

    /** Title of a calendar period (week = "first–last", each with the week format). */
    function calendarTitle(view, id, zone, titles) {
        let start = periodStart(view, id, zone);
        if (start === null) {
            return "";
        }
        let fmt = titleFormat(titles, view);
        if (view === "week") {
            let last = start.plus({days: 6});
            return formatDate(fmt, start, titles) + "\u2013" + formatDate(fmt, last, titles);
        }
        return formatDate(fmt, start, titles);
    }

    /** Title of a rolling window [startMs, endMs]: date range formatted with the day format. */
    function rollingTitle(startMs, endMs, zone, titles) {
        let fmt = titleFormat(titles, "day");
        let start = DateTime.fromMillis(startMs, {zone: zone});
        let end = DateTime.fromMillis(endMs, {zone: zone});
        return formatDate(fmt, start, titles) + "\u2013" + formatDate(fmt, end, titles);
    }

    /** Nominal rolling window ending at `nowMs` (N × 86400 s, no rounding). */
    function rollingWindow(view, nowMs) {
        return {start: nowMs - ROLLING_DAYS[view] * 86400000, end: nowMs};
    }

    /**
     * Resolves a requested route against the current state.
     * route: {view, id} (id null = rolling for week/month/year, default for day).
     * Returns {view, id, rolling, replace} where `replace` signals that the hash must be rewritten.
     */
    function resolveRoute(route, ctx) {
        if (route === null) {
            return {view: "live", id: null, rolling: false, replace: true};
        }
        if (route.view === "live") {
            return {view: "live", id: null, rolling: false, replace: false};
        }
        let view = route.view;
        let currentId = periodIdAt(view, ctx.nowMs, ctx.zone, ctx.weekStart);
        if (route.id === null) {
            if (view === "day") {
                return {view: view, id: ctx.defaultDayId || currentId, rolling: false, replace: true};
            }
            return {view: view, id: null, rolling: true, replace: false};
        }
        if (!isValidId(view, route.id, ctx.zone, ctx.weekStart) || compareIds(route.id, currentId) > 0) {
            if (view === "day") {
                return {view: view, id: ctx.defaultDayId || currentId, rolling: false, replace: true};
            }
            return {view: view, id: null, rolling: true, replace: true};
        }
        return {view: view, id: route.id, rolling: false, replace: false};
    }

    return {
        VIEWS: VIEWS,
        PERIOD_VIEWS: PERIOD_VIEWS,
        ROLLING_VIEWS: ROLLING_VIEWS,
        ROLLING_DAYS: ROLLING_DAYS,
        zoneName: zoneName,
        isPeriodView: isPeriodView,
        hasRolling: hasRolling,
        isValidIdFormat: isValidIdFormat,
        isValidId: isValidId,
        periodStart: periodStart,
        periodEnd: periodEnd,
        periodIdAt: periodIdAt,
        shiftId: shiftId,
        compareIds: compareIds,
        neighbourId: neighbourId,
        parseHash: parseHash,
        formatHash: formatHash,
        formatDate: formatDate,
        calendarTitle: calendarTitle,
        rollingTitle: rollingTitle,
        rollingWindow: rollingWindow,
        resolveRoute: resolveRoute,
    };
}));
