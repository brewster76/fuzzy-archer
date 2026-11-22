"use strict";
// node --test tests/js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const jsDir = path.join(__dirname, "..", "..", "skins", "Bootstrap", "js");
const sandbox = {};
vm.runInNewContext(fs.readFileSync(path.join(jsDir, "luxon.min.js"), "utf8") + "\nthis.luxon = luxon;", sandbox);
const luxon = sandbox.luxon;
const core = require(path.join(jsDir, "periodcore.js"))(luxon);

const BERLIN = "Europe/Berlin";
const ms = (iso) => luxon.DateTime.fromISO(iso, {zone: BERLIN}).toMillis();

const TITLES = {
    day: "%d.%m.%Y", week: "%d.%m.%Y", month: "%B %Y", year: "%Y",
    month_names: ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
    month_abbr: ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"],
    day_names: ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    day_abbr: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
};

test("zoneName", () => {
    assert.equal(core.zoneName("Europe/Berlin"), "Europe/Berlin");
    assert.equal(core.zoneName("+01:00"), "UTC+01:00");
    assert.equal(core.zoneName("-05:30"), "UTC-05:30");
    assert.equal(core.zoneName(undefined), "local");
    assert.ok(luxon.DateTime.now().setZone(core.zoneName("+01:00")).isValid);
});

test("parseHash / formatHash", () => {
    assert.deepEqual(core.parseHash(""), {view: "live", id: null});
    assert.deepEqual(core.parseHash("#"), {view: "live", id: null});
    assert.deepEqual(core.parseHash("#live"), {view: "live", id: null});
    assert.deepEqual(core.parseHash("#week"), {view: "week", id: null});
    assert.deepEqual(core.parseHash("#week/"), {view: "week", id: null});
    assert.deepEqual(core.parseHash("#day/20261118"), {view: "day", id: "20261118"});
    assert.deepEqual(core.parseHash("#month/202611"), {view: "month", id: "202611"});
    assert.deepEqual(core.parseHash("#month/20190611"), {view: "month", id: "20190611"});
    assert.deepEqual(core.parseHash("#year/2026"), {view: "year", id: "2026"});
    assert.deepEqual(core.parseHash("#year/202511"), {view: "year", id: "202511"});
    assert.deepEqual(core.parseHash("#year/25"), {view: "year", id: "25"});
    assert.equal(core.parseHash("#menu"), null);
    assert.equal(core.parseHash("#day/2026"), null);
    assert.equal(core.parseHash("#year/../x"), null);
    assert.equal(core.parseHash("#day/20261118/x"), null);
    assert.equal(core.formatHash("live", null), "");
    assert.equal(core.formatHash("week", null), "#week");
    assert.equal(core.formatHash("day", "20261118"), "#day/20261118");
});

test("period ids at instants, week_start", () => {
    const t = ms("2026-11-18T12:00");  // Wednesday
    assert.equal(core.periodIdAt("day", t, BERLIN, 6), "20261118");
    assert.equal(core.periodIdAt("week", t, BERLIN, 6), "20261115");  // Sunday start
    assert.equal(core.periodIdAt("week", t, BERLIN, 0), "20261116");  // Monday start
    assert.equal(core.periodIdAt("week", ms("2026-11-15T00:00"), BERLIN, 6), "20261115");
    assert.equal(core.periodIdAt("week", ms("2026-11-14T23:59"), BERLIN, 6), "20261108");
    assert.equal(core.periodIdAt("month", t, BERLIN, 6), "202611");
    assert.equal(core.periodIdAt("year", t, BERLIN, 6), "2026");
    const utcLate = luxon.DateTime.fromISO("2026-11-18T23:30Z").toMillis();
    assert.equal(core.periodIdAt("day", utcLate, BERLIN, 6), "20261119");
    assert.equal(core.periodIdAt("day", utcLate, "UTC", 6), "20261118");
});

test("id validation", () => {
    assert.ok(core.isValidId("day", "20240229", BERLIN, 6));
    assert.ok(!core.isValidId("day", "20230229", BERLIN, 6));
    assert.ok(!core.isValidId("month", "202613", BERLIN, 6));
    assert.ok(core.isValidId("week", "20261115", BERLIN, 6));
    assert.ok(!core.isValidId("week", "20261116", BERLIN, 6));
    assert.ok(core.isValidId("week", "20261116", BERLIN, 0));
    assert.ok(!core.isValidId("year", "26", BERLIN, 6));
});

test("normalizeId canonicalizes year, month, and week date URLs", () => {
    assert.equal(core.normalizeId("year", "202511", BERLIN, 6), "2025");
    assert.equal(core.normalizeId("month", "20190611", BERLIN, 6), "201906");
    assert.equal(core.normalizeId("week", "20261027", BERLIN, 0), "20261026");
    assert.equal(core.normalizeId("week", "20261027", BERLIN, 6), "20261025");
    assert.equal(core.normalizeId("month", "201913", BERLIN, 6), null);
    assert.equal(core.normalizeId("week", "20260230", BERLIN, 6), null);
    assert.equal(core.normalizeId("year", "25", BERLIN, 6), null);
});

test("period prefixes resolve to local calendar-year and month ranges", () => {
    const year = core.prefixRange("week", "2019", BERLIN);
    assert.equal(year.start.toISO(), "2019-01-01T00:00:00.000+01:00");
    assert.equal(year.end.toISO(), "2020-01-01T00:00:00.000+01:00");
    const month = core.prefixRange("week", "201910", BERLIN);
    assert.equal(month.start.toISO(), "2019-10-01T00:00:00.000+02:00");
    assert.equal(month.end.toISO(), "2019-11-01T00:00:00.000+01:00");
    assert.equal(core.prefixRange("month", "201910", BERLIN), null);
});

test("calendar spans are local, 23/25 h days", () => {
    const span = (view, id) => (core.periodEnd(view, id, BERLIN) - core.periodStart(view, id, BERLIN)) / 3600000;
    assert.equal(span("day", "20260329"), 23);
    assert.equal(span("day", "20261025"), 25);
    assert.equal(span("day", "20261118"), 24);
    assert.equal(span("week", "20260329"), 7 * 24 - 1);
    assert.equal(core.periodStart("month", "202611", BERLIN).toISO(), "2026-11-01T00:00:00.000+01:00");
    assert.equal(core.periodEnd("year", "2026", BERLIN).toISO(), "2027-01-01T00:00:00.000+01:00");
});

test("midnight DST gap starts at first existing instant", () => {
    // America/Santiago 2022-09-11: 00:00 -> 01:00
    const start = core.periodStart("day", "20220911", "America/Santiago");
    assert.equal(start.hour, 1);
    assert.equal(start.day, 11);
});

test("shiftId and neighbourId", () => {
    assert.equal(core.shiftId("day", "20261231", 1, BERLIN), "20270101");
    assert.equal(core.shiftId("week", "20261025", 1, BERLIN), "20261101");
    assert.equal(core.shiftId("week", "20261101", -1, BERLIN), "20261025");
    assert.equal(core.shiftId("month", "202601", -1, BERLIN), "202512");
    assert.equal(core.shiftId("year", "2026", 1, BERLIN), "2027");

    const available = new Set(["20261110", "20261114", "20261118"]);
    const sel = (id) => available.has(id);
    assert.equal(core.neighbourId("day", "20261118", -1, BERLIN, "20261118", null, sel), "20261114");
    assert.equal(core.neighbourId("day", "20261114", -1, BERLIN, "20261118", null, sel), "20261110");
    assert.equal(core.neighbourId("day", "20261110", -1, BERLIN, "20261118", "20261105", sel), null);
    assert.equal(core.neighbourId("day", "20261118", 1, BERLIN, "20261118", null, sel), null);
    assert.equal(core.neighbourId("day", "20261117", 1, BERLIN, "20261118", null), "20261118");
});

test("formatDate tokens and titles", () => {
    const dt = luxon.DateTime.fromISO("2026-03-05T10:00", {zone: BERLIN});
    assert.equal(core.formatDate("%d.%m.%Y %e %y %b %B %a %A %% %H", dt, TITLES),
        "05.03.2026 5 26 Mär März Do Donnerstag % %H");
    assert.equal(core.calendarTitle("day", "20261118", BERLIN, TITLES), "18.11.2026");
    assert.equal(core.calendarTitle("week", "20261116", BERLIN, TITLES), "16.11.2026\u201322.11.2026");
    assert.equal(core.calendarTitle("month", "202611", BERLIN, TITLES), "November 2026");
    assert.equal(core.calendarTitle("year", "2026", BERLIN, TITLES), "2026");
    assert.equal(core.calendarTitle("month", "202611", BERLIN, {month: "%m/%Y"}), "11/2026");
    assert.equal(core.calendarTitle("day", "20261118", BERLIN, null), "18.11.2026");
});

test("rolling windows are exactly N x 86400 s", () => {
    const now = ms("2026-03-30T10:07");  // after DST change
    for (const [view, days] of Object.entries({week: 8, month: 32, year: 367})) {
        const w = core.rollingWindow(view, now);
        assert.equal(w.end - w.start, days * 86400000);
    }
    const w = core.rollingWindow("week", now);
    assert.equal(core.rollingTitle(w.start, w.end, BERLIN, TITLES), "22.03.2026\u201330.03.2026");
});

test("resolveRoute", () => {
    const ctx = {nowMs: ms("2026-11-18T12:00"), zone: BERLIN, weekStart: 6, defaultDayId: null};
    const r = (view, id, c) => core.resolveRoute({view: view, id: id}, c || ctx);
    assert.deepEqual(r("live", null), {view: "live", id: null, rolling: false, replace: false});
    assert.deepEqual(core.resolveRoute(null, ctx), {view: "live", id: null, rolling: false, replace: true});
    assert.deepEqual(r("day", null), {view: "day", id: "20261118", rolling: false, replace: true});
    assert.deepEqual(r("day", null, {...ctx, defaultDayId: "20261117"}), {view: "day", id: "20261117", rolling: false, replace: true});
    assert.deepEqual(r("day", "20261101"), {view: "day", id: "20261101", rolling: false, replace: false});
    assert.deepEqual(r("day", "20261119"), {view: "day", id: "20261118", rolling: false, replace: true});
    assert.deepEqual(r("week", null), {view: "week", id: null, rolling: true, replace: false});
    assert.deepEqual(r("week", "20261116"), {view: "week", id: "20261116", rolling: false, replace: false, invalid: true});
    assert.deepEqual(r("week", "20261115"), {view: "week", id: "20261115", rolling: false, replace: false});
    assert.deepEqual(r("month", "202612"), {view: "month", id: "202612", rolling: false, replace: false});
    assert.deepEqual(r("year", "2025"), {view: "year", id: "2025", rolling: false, replace: false});
    assert.deepEqual(r("year", "2027"), {view: "year", id: "2027", rolling: false, replace: false});
    assert.deepEqual(r("month", "202613"), {view: "month", id: "202613", rolling: false, replace: false, invalid: true});
});

test("resolveRoute preserves explicit period ids when history generation is disabled", () => {
    const ctx = {nowMs: ms("2026-11-18T12:00"), zone: BERLIN, weekStart: 6, generateHistory: false};
    const r = (view, id) => core.resolveRoute({view: view, id: id}, ctx);
    assert.deepEqual(r("day", "20261101"), {view: "day", id: "20261118", rolling: false, replace: true});
    assert.deepEqual(r("day", "20261118"), {view: "day", id: "20261118", rolling: false, replace: false});
    assert.deepEqual(r("week", "20261115"), {view: "week", id: "20261115", rolling: false, replace: false});
    assert.deepEqual(r("month", "202611"), {view: "month", id: "202611", rolling: false, replace: false});
    assert.deepEqual(r("year", null), {view: "year", id: null, rolling: true, replace: false});
    assert.deepEqual(r("year", "2025"), {view: "year", id: "2025", rolling: false, replace: false});
});
