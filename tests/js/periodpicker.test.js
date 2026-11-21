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
const picker = require(path.join(jsDir, "periodpicker.js"))(core, luxon);

const BERLIN = "Europe/Berlin";

function makeCtx(overrides) {
    const entries = {
        day: {"20261117": {s: "ok"}, "20261118": {s: "gaps"}, "20261116": {s: "error"}},
        week: {"20261109": {s: "ok"}, "20261102": {s: "incompatible"}},
        month: {"202610": {s: "ok"}},
        year: {"2025": {s: "ok"}},
    };
    const current = {day: "20261119", week: "20261116", month: "202611", year: "2026"};
    const first = {day: "20261101", week: "20261026", month: "202610", year: "2025"};
    return Object.assign({
        zone: BERLIN,
        weekStart: 0,
        selectedId: null,
        currentId: (view) => current[view],
        firstId: (view) => first[view],
        entry: (view, id) => entries[view][id] || {s: "pending"},
    }, overrides || {});
}

test("cellState covers running, future, before first and manifest states", () => {
    const ctx = makeCtx();
    assert.equal(picker.cellState("day", "20261119", ctx), "running");
    assert.equal(picker.cellState("day", "20261120", ctx), "future");
    assert.equal(picker.cellState("day", "20261031", ctx), "nodata");
    assert.equal(picker.cellState("day", "20261117", ctx), "ok");
    assert.equal(picker.cellState("day", "20261118", ctx), "gaps");
    assert.equal(picker.cellState("day", "20261116", ctx), "error");
    assert.equal(picker.cellState("day", "20261115", ctx), "pending");
    const empty = makeCtx({entry: () => null});
    assert.equal(picker.cellState("day", "20261115", empty), "unknown");
});

test("day grid starts at week_start and marks selectable cells", () => {
    const m = picker.model("day", "202611", makeCtx({selectedId: "20261117"}));
    assert.equal(m.kind, "days");
    assert.deepEqual(m.weekdays, [0, 1, 2, 3, 4, 5, 6]);
    // 1 Nov 2026 is a Sunday -> first row starts Monday 26 Oct
    assert.equal(m.rows[0].cells[0].id, "20261026");
    assert.equal(m.rows[0].cells[0].inMonth, false);
    assert.equal(m.rows[m.rows.length - 1].cells[6].id, "20261206");
    const cells = Object.fromEntries(m.rows.flatMap((r) => r.cells).map((c) => [c.id, c]));
    assert.equal(cells["20261117"].selectable, true);
    assert.equal(cells["20261117"].selected, true);
    assert.equal(cells["20261118"].selectable, true);
    assert.equal(cells["20261119"].selectable, true);
    assert.equal(cells["20261120"].selectable, false);
    assert.equal(cells["20261116"].selectable, false);
    assert.equal(cells["20261115"].selectable, false);
    assert.equal(m.prev, null);   // first archive month
    assert.equal(m.next, null);   // running month
});

test("week grid honours week_start = Sunday and uses row ids", () => {
    const ctx = makeCtx({weekStart: 6, currentId: (v) => ({week: "20261115", day: "20261119"})[v],
        firstId: () => "20261025"});
    const m = picker.model("week", "202611", ctx);
    assert.deepEqual(m.weekdays, [6, 0, 1, 2, 3, 4, 5]);
    assert.equal(m.rows[0].id, "20261101");
    assert.equal(m.rows[0].cells[0].id, "20261101");
    const row = m.rows.find((r) => r.id === "20261115");
    assert.equal(row.state, "running");
    assert.equal(row.selectable, true);
    assert.equal(m.rows.find((r) => r.id === "20261122").state, "future");
});

test("week state comes from the week manifest", () => {
    const m = picker.model("week", "202611", makeCtx());
    const byId = Object.fromEntries(m.rows.map((r) => [r.id, r]));
    assert.equal(byId["20261026"].state, "pending");
    assert.equal(byId["20261102"].state, "incompatible");
    assert.equal(byId["20261102"].selectable, false);
    assert.equal(byId["20261109"].selectable, true);
    assert.equal(m.prev, "202610");
});

test("month and year grids with navigation bounds", () => {
    const months = picker.model("month", "2026", makeCtx());
    assert.equal(months.cells.length, 12);
    assert.equal(months.cells[0].state, "nodata");
    assert.equal(months.cells[9].state, "ok");
    assert.equal(months.cells[10].state, "running");
    assert.equal(months.cells[11].state, "future");
    assert.equal(months.prev, null);
    assert.equal(months.next, null);

    const ctx = makeCtx({firstId: (v) => (v === "year" ? "2001" : null)});
    assert.equal(picker.cursorFor("year", "2026", ctx), "2026");
    assert.equal(picker.cursorFor("year", "2015", ctx), "2026");
    assert.equal(picker.cursorFor("year", "2014", ctx), "2014");
    const years = picker.model("year", "2026", ctx);
    assert.equal(years.from, 2015);
    assert.equal(years.cells[11].state, "running");
    assert.equal(years.prev, "2014");
    assert.equal(years.next, null);
    const older = picker.model("year", "2014", ctx);
    assert.equal(older.prev, "2002");
    assert.equal(picker.model("year", "2002", ctx).prev, null);
});

test("cursorFor and shiftCursor", () => {
    const ctx = makeCtx();
    assert.equal(picker.cursorFor("day", "20261117", ctx), "202611");
    assert.equal(picker.cursorFor("week", "20261026", ctx), "202610");
    assert.equal(picker.cursorFor("month", "202611", ctx), "2026");
    assert.equal(picker.shiftCursor("day", "202601", -1, BERLIN), "202512");
    assert.equal(picker.shiftCursor("month", "2026", 1, BERLIN), "2027");
    assert.equal(picker.shiftCursor("year", "2026", -1, BERLIN), "2014");
});
