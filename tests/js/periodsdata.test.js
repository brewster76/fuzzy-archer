"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = path.join(__dirname, "..", "..", "skins", "Bootstrap", "js", "periodsdata.js");
const source = fs.readFileSync(sourcePath, "utf8");

async function prepare(generateHistory) {
    const calls = [];
    const store = {
        current: null,
        manifest: null,
        fetchCurrent: async function () {
            calls.push("current");
            this.current = {};
        },
        fetchManifest: async function () {
            calls.push("manifest");
            this.manifest = {};
        },
    };
    const views = {
        ctx: {config: {generate_history: generateHistory}},
        hooks: {isSelectable: {}, firstId: {}, renderers: []},
        state: {view: "week"},
    };
    const sandbox = {
        PeriodCore: {PERIOD_VIEWS: ["day", "week", "month", "year"], isPeriodView: () => true},
        PeriodViews: views,
        PeriodStore: {createStore: () => store},
        document: {addEventListener: () => {}},
    };
    vm.runInNewContext(source + "\nthis.periodData = PeriodData;", sandbox);
    await views.hooks.prepare({config: {data_url: "historic_data"}, zone: "UTC", weekStart: 0});
    return calls;
}

test("period data loads mutable index only when historical generation is disabled", async () => {
    assert.deepEqual(await prepare(false), ["current"]);
});

test("period data loads the manifest when historical generation is enabled", async () => {
    assert.deepEqual(await prepare(true), ["current", "manifest"]);
});

test("route preload fetches only the manifest segments the route needs", async () => {
    const luxonBox = {};
    vm.runInNewContext(fs.readFileSync(path.join(path.dirname(sourcePath), "luxon.min.js"), "utf8") + "\nthis.luxon = luxon;", luxonBox);
    const core = require(path.join(path.dirname(sourcePath), "periodcore.js"))(luxonBox.luxon);
    const S = require(path.join(path.dirname(sourcePath), "periodstore.js"))(core);
    const files = {
        "manifest.json": {archive: {first: 1000000000}, segments: {day: {"2015": "a", "2016": "b"}, week: {"2015": "c", "2016": "d"}, year: {all: "y"}}},
        "current.json": {current: {}, rolling: {}},
    };
    const calls = [];
    const fetchFn = async (url) => {
        calls.push(url.split("?")[0]);
        const name = url.replace(/^historic_data\//, "").split("?")[0];
        const obj = files[name] || {entries: {}};
        const buf = Buffer.from(JSON.stringify(obj));
        return {ok: true, status: 200, arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)};
    };
    const views = {
        ctx: {config: {generate_history: true}, zone: "UTC", weekStart: 6},
        hooks: {isSelectable: {}, firstId: {}, renderers: []},
        state: {view: "year"},
    };
    const sandbox = {
        PeriodCore: core,
        PeriodViews: views,
        PeriodStore: {createStore: (o) => S.createStore(Object.assign({}, o, {fetchFn}))},
        document: {addEventListener: () => {}},
        console: console,
    };
    vm.runInNewContext(source, sandbox);
    await views.hooks.prepare({config: {data_url: "historic_data"}, zone: "UTC", weekStart: 6});
    assert.deepEqual(calls.sort(), ["historic_data/current.json", "historic_data/manifest.json"]);
    calls.length = 0;
    await views.hooks.preload({view: "year", id: "2016"});
    assert.deepEqual(calls, ["historic_data/manifest/year/all.json"]);
    assert.equal(views.hooks.preload({view: "year", id: "2016"}), null);   // cached for the session
    assert.equal(views.hooks.preload({view: "year", id: null}), null);     // rolling needs no segment
    calls.length = 0;
    await views.hooks.preload({view: "week", id: "2016"});                  // prefix: weeks may start in 2015
    assert.deepEqual(calls.sort(), ["historic_data/manifest/week/2015.json", "historic_data/manifest/week/2016.json"]);
    calls.length = 0;
    await views.hooks.preload({view: "day", id: null});                     // default day: newest segment
    assert.deepEqual(calls, ["historic_data/manifest/day/2016.json"]);
});
