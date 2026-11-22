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
