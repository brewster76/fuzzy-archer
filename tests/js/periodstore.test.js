"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const zlib = require("node:zlib");

const jsDir = path.join(__dirname, "..", "..", "skins", "Bootstrap", "js");
const sandbox = {};
vm.runInNewContext(fs.readFileSync(path.join(jsDir, "luxon.min.js"), "utf8") + "\nthis.luxon = luxon;", sandbox);
const core = require(path.join(jsDir, "periodcore.js"))(sandbox.luxon);
const S = require(path.join(jsDir, "periodstore.js"))(core);

const BERLIN = "Europe/Berlin";
const ms = (iso) => sandbox.luxon.DateTime.fromISO(iso, {zone: BERLIN}).toMillis();
const sec = (iso) => ms(iso) / 1000;

function body(obj, gzip) {
    const raw = Buffer.from(JSON.stringify(obj), "utf8");
    return gzip ? zlib.gzipSync(raw) : raw;
}

/** Fake server: path -> object | {status}; records requested URLs. */
function server(files, options) {
    const calls = [];
    const fetchFn = async (url) => {
        calls.push(url);
        if (options && options.delay) {
            await new Promise((r) => setTimeout(r, options.delay));
        }
        const p = url.replace(/^data\//, "").split("?")[0];
        const f = files[p];
        if (f === undefined || f.status) {
            return {ok: false, status: f ? f.status : 404};
        }
        const buf = body(f, p.endsWith(".gz"));
        return {ok: true, status: 200, arrayBuffer: async () => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)};
    };
    return {fetchFn, calls};
}

const CURRENT = {
    schema_version: 1, generated: sec("2026-11-21T18:00"), week_start: 6,
    current: {
        day: {period_id: "20261121", file: "current/day.json.gz", rev: "d1", generated: sec("2026-11-21T18:00"), refresh: 300},
        week: {period_id: "20261115", file: "current/week.json.gz", rev: "w1", generated: sec("2026-11-21T17:00"), refresh: 3600},
        month: {period_id: "202611", file: "current/month.json.gz", rev: "m1", generated: sec("2026-11-21T15:00"), refresh: 10800},
        year: {period_id: "2026", file: "current/year.json.gz", rev: "y1", generated: sec("2026-11-21T12:00"), refresh: 21600},
    },
    rolling: {
        week: {file: "rolling/week.json.gz", rev: "rw1", generated: sec("2026-11-21T17:00"), refresh: 3600},
    },
};
const MANIFEST = {
    schema_version: 1, generated: 1, week_start: 6,
    archive: {first: sec("2025-12-30T00:05"), last: sec("2026-11-21T18:00")},
    backfill: {state: "running", done: 1, total: 2, updated: 1},
    segments: {day: {"2025": "s25", "2026": "s26"}, week: {}, month: {}, year: {all: "ya"}},
};
const DAY26 = {schema_version: 1, period: "day", segment: "2026", entries: {
    "20261118": {s: "ok", rev: "a", file: "day/20261118.json.gz"},
    "20261119": {s: "gaps", rev: "b", file: "day/20261119.json.gz", missing: ["wx_binding/UV"]},
    "20261120": {s: "error", tries: 3},
}};
const DAY25 = {schema_version: 1, period: "day", segment: "2025", entries: {"20251231": {s: "ok", rev: "c", file: "day/20251231.json.gz"}}};

function files(extra) {
    return Object.assign({
        "current.json": CURRENT,
        "manifest.json": MANIFEST,
        "manifest/day/2026.json": DAY26,
        "manifest/day/2025.json": DAY25,
        "manifest/year/all.json": {entries: {"2025": {s: "nodata"}}},
        "day/20261118.json.gz": {period: "day", period_id: "20261118", kind: "calendar"},
        "current/day.json.gz": {period: "day", period_id: "20261121", kind: "calendar", generated: 5},
        "rolling/week.json.gz": {period: "week", period_id: null, kind: "rolling"},
    }, extra || {});
}

test("LRU evicts least recently used", () => {
    const lru = new S.LRU(2);
    lru.set("a", 1); lru.set("b", 2);
    assert.equal(lru.get("a"), 1);
    lru.set("c", 3);
    assert.ok(lru.has("a") && lru.has("c") && !lru.has("b"));
    assert.equal(lru.size, 2);
});

test("decodeBody handles gzip and already decoded bodies", async () => {
    const obj = {a: [1, 2, "ä"]};
    const gz = body(obj, true);
    assert.ok(S.isGzip(new Uint8Array(gz)));
    assert.deepEqual(await S.decodeBody(gz), obj);
    assert.deepEqual(await S.decodeBody(body(obj, false)), obj);
    await assert.rejects(S.decodeBody(Buffer.from("not json")));
});

test("backoff is bounded, segment keys, url join", () => {
    assert.equal(S.backoffDelay(0, 5000, 600000), 5000);
    assert.equal(S.backoffDelay(3, 5000, 600000), 40000);
    assert.equal(S.backoffDelay(20, 5000, 600000), 600000);
    assert.equal(S.segmentKey("day", "20261118"), "2026");
    assert.equal(S.segmentKey("week", "20251228"), "2025");
    assert.equal(S.segmentKey("year", "2026"), "all");
    assert.equal(S.joinUrl("../historic_data/", "/day/x.json.gz"), "../historic_data/day/x.json.gz");
});

test("manifest entries, derived states and selectability", async () => {
    const srv = server(files());
    const store = S.createStore({base: "data", fetchFn: srv.fetchFn, zone: BERLIN, weekStart: 6});
    await Promise.all([store.fetchCurrent(), store.fetchManifest()]);
    assert.equal(store.entry("day", "20261118").s, "ok");
    assert.equal(store.entry("day", "20261117").s, "pending");     // no entry, inside archive
    assert.equal(store.entry("day", "20251229").s, "nodata");      // before archive.first
    assert.equal(store.entry("day", "20251230").s, "pending");
    assert.ok(store.isSelectable("day", "20261118"));
    assert.ok(store.isSelectable("day", "20261119"));
    assert.ok(!store.isSelectable("day", "20261120"));
    assert.ok(store.isSelectable("day", "20261121"));              // running period from current.json
    assert.equal(store.firstId("day"), "20251230");
    assert.equal(store.firstId("week"), "20251228");
    assert.equal(store.newestId("day"), "20261119");
    assert.equal(store.currentPeriodId("week"), "20261115");
    // unchanged segment revs are not fetched again
    const before = srv.calls.length;
    await store.fetchManifest();
    assert.equal(srv.calls.length - before, 1);
    assert.ok(srv.calls.every((u) => u.startsWith("data/")));
});

test("firstAvailableId selects the earliest loadable period overlapping a prefix range", async () => {
    const f = files({
        "manifest.json": Object.assign({}, MANIFEST, {segments: {
            week: {"2018": "w18", "2019": "w19"},
            month: {"2019": "m19"},
        }}),
        "manifest/week/2018.json": {entries: {"20181230": {s: "ok", rev: "a", file: "week/20181230.json.gz"}}},
        "manifest/week/2019.json": {entries: {
            "20190929": {s: "gaps", rev: "b", file: "week/20190929.json.gz"},
            "20191006": {s: "ok", rev: "c", file: "week/20191006.json.gz"},
            "20191103": {s: "pending"},
        }},
        "manifest/month/2019.json": {entries: {
            "201906": {s: "ok", rev: "d", file: "month/201906.json.gz"},
            "201912": {s: "gaps", rev: "e", file: "month/201912.json.gz"},
        }},
    });
    const srv = server(f);
    const store = S.createStore({base: "data", fetchFn: srv.fetchFn, zone: BERLIN, weekStart: 6});
    await Promise.all([store.fetchCurrent(), store.fetchManifest()]);
    const year = core.prefixRange("week", "2019", BERLIN);
    const october = core.prefixRange("week", "201910", BERLIN);
    const monthYear = core.prefixRange("month", "2019", BERLIN);
    assert.equal(store.firstAvailableId("week", year.start.toMillis(), year.end.toMillis()), "20181230");
    assert.equal(store.firstAvailableId("week", october.start.toMillis(), october.end.toMillis()), "20190929");
    assert.equal(store.firstAvailableId("month", monthYear.start.toMillis(), monthYear.end.toMillis()), "201906");
    assert.equal(store.firstAvailableId("month", Date.UTC(2020, 0), Date.UTC(2021, 0)), null);
});

test("source resolution", async () => {
    const srv = server(files());
    const store = S.createStore({base: "data", fetchFn: srv.fetchFn, zone: BERLIN, weekStart: 6});
    assert.deepEqual(store.source("day", "20261118", false), {kind: "status", status: "unknown"});
    await Promise.all([store.fetchCurrent(), store.fetchManifest()]);
    assert.equal(store.source("week", null, true).kind, "mutable");
    assert.deepEqual(store.source("month", null, true), {kind: "status", status: "unknown"});
    assert.equal(store.source("day", "20261121", false).file, "current/day.json.gz");
    const h = store.source("day", "20261119", false);
    assert.deepEqual(h, {kind: "historic", file: "day/20261119.json.gz", rev: "b", state: "gaps", missing: ["wx_binding/UV"]});
    assert.deepEqual(store.source("day", "20261120", false), {kind: "status", status: "error"});
    assert.deepEqual(store.source("day", "20261117", false), {kind: "status", status: "pending"});
    assert.deepEqual(store.source("year", "2025", false), {kind: "status", status: "nodata"});
});

test("rolling-only index serves today's day and all rolling views without a manifest", async () => {
    const now = sec("2026-11-21T18:00");
    const index = {
        schema_version: 1,
        generated: now,
        week_start: 6,
        current: {
            day: {period_id: "20261121", file: "current/day.json.gz", rev: "day1", generated: now, refresh: 300},
        },
        rolling: {
            week: {file: "rolling/week.json.gz", rev: "week1", generated: now, refresh: 3600},
            month: {file: "rolling/month.json.gz", rev: "month1", generated: now, refresh: 10800},
            year: {file: "rolling/year.json.gz", rev: "year1", generated: now, refresh: 21600},
        },
    };
    const srv = server({
        "current.json": index,
        "current/day.json.gz": {period: "day", period_id: "20261121", kind: "calendar"},
        "rolling/week.json.gz": {period: "week", kind: "rolling"},
        "rolling/month.json.gz": {period: "month", kind: "rolling"},
        "rolling/year.json.gz": {period: "year", kind: "rolling"},
    });
    const store = S.createStore({base: "data", fetchFn: srv.fetchFn, zone: BERLIN, weekStart: 6});
    await store.fetchCurrent();
    assert.equal(store.source("day", "20261121", false).kind, "mutable");
    for (const view of ["week", "month", "year"]) {
        assert.equal(store.source(view, null, true).kind, "mutable");
    }
    assert.equal(srv.calls.length, 1);
    assert.equal(store.manifest, null);
});

test("selected running period is kept after a period change until its final file exists", async () => {
    const f = files();
    const srv = server(f);
    const store = S.createStore({base: "data", fetchFn: srv.fetchFn, zone: BERLIN, weekStart: 6});
    await Promise.all([store.fetchCurrent(), store.fetchManifest()]);
    const src = store.source("day", "20261121", false);
    await store.loadMutable(src.file, src.rev);
    // midnight: current.json now points to the 22nd, the 21st is not yet in the manifest
    f["current.json"] = JSON.parse(JSON.stringify(CURRENT));
    f["current.json"].current.day = {period_id: "20261122", file: "current/day.json.gz", rev: "d2", generated: 9, refresh: 300};
    f["current/day.json.gz"] = {period: "day", period_id: "20261122", kind: "calendar"};
    await store.fetchCurrent();
    await store.loadMutable("current/day.json.gz", "d2");
    const kept = store.source("day", "20261121", false);
    assert.equal(kept.kind, "retained");
    assert.equal(kept.data.period_id, "20261121");
    // worker publishes the completed day
    f["manifest.json"] = Object.assign({}, MANIFEST, {segments: Object.assign({}, MANIFEST.segments, {day: {"2025": "s25", "2026": "s26b"}})});
    f["manifest/day/2026.json"] = {entries: Object.assign({}, DAY26.entries, {"20261121": {s: "ok", rev: "z", file: "day/20261121.json.gz"}})};
    await store.fetchManifest();
    assert.equal(store.source("day", "20261121", false).kind, "historic");
});

test("historic LRU cache, in-flight de-duplication and no caching of failures", async () => {
    const f = files();
    for (let d = 1; d <= 5; d++) {
        f["day/2026110" + d + ".json.gz"] = {period_id: "2026110" + d};
    }
    const srv = server(f, {delay: 5});
    const store = S.createStore({base: "data", fetchFn: srv.fetchFn, zone: BERLIN, weekStart: 6, maxEntries: 3});
    const [a, b] = await Promise.all([store.loadHistoric("day/20261101.json.gz", "r"), store.loadHistoric("day/20261101.json.gz", "r")]);
    assert.equal(a, b);
    assert.equal(srv.calls.length, 1);
    await store.loadHistoric("day/20261101.json.gz", "r");
    assert.equal(srv.calls.length, 1);
    assert.equal(srv.calls[0], "data/day/20261101.json.gz?r=r");
    // new rev = new cache key (regeneration)
    await store.loadHistoric("day/20261101.json.gz", "r2");
    assert.equal(srv.calls.length, 2);
    for (let d = 2; d <= 5; d++) {
        await store.loadHistoric("day/2026110" + d + ".json.gz", "r");
    }
    assert.equal(store.cacheSize(), 3);
    // failures are not cached
    await assert.rejects(store.loadHistoric("day/20991231.json.gz", "x"), (e) => e.status === 404);
    await assert.rejects(store.loadHistoric("day/20991231.json.gz", "x"));
    assert.equal(srv.calls.filter((u) => u.includes("20991231")).length, 2);
    // mutable files are reloaded only on rev change and do not count against the LRU
    const before = srv.calls.length;
    await store.loadMutable("current/day.json.gz", "d1");
    await store.loadMutable("current/day.json.gz", "d1");
    assert.equal(srv.calls.length - before, 1);
    assert.equal(store.cacheSize(), 3);
});
