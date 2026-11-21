/*
 * Data access of the period views (no DOM access): gzip decoding, LRU cache for immutable period
 * files, separate cache for mutable (current/rolling) files, in-flight de-duplication, manifest
 * segments and selectability. Contract: docs/historic-data-contract.md §2–§5.
 * Browser: global `PeriodStore` (needs `PeriodCore`); node:test: module.exports(core).
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory;
    } else {
        root.PeriodStore = factory(root.PeriodCore);
    }
}(typeof self !== "undefined" ? self : this, function (core) {
    "use strict";

    const LOADABLE = {ok: true, gaps: true};

    class HttpError extends Error {
        constructor(status, url) {
            super("HTTP " + status + " " + url);
            this.status = status;
            this.url = url;
        }
    }

    /** Least recently used map with a fixed number of entries. */
    class LRU {
        constructor(max) {
            this.max = max;
            this.map = new Map();
        }
        get(key) {
            if (!this.map.has(key)) {
                return undefined;
            }
            let value = this.map.get(key);
            this.map.delete(key);
            this.map.set(key, value);
            return value;
        }
        has(key) {
            return this.map.has(key);
        }
        set(key, value) {
            this.map.delete(key);
            this.map.set(key, value);
            while (this.map.size > this.max) {
                this.map.delete(this.map.keys().next().value);
            }
        }
        get size() {
            return this.map.size;
        }
    }

    function isGzip(bytes) {
        return bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
    }

    /** ArrayBuffer → parsed JSON; gzip only if the magic bytes are present (server may have decoded it). */
    async function decodeBody(buffer) {
        let bytes = new Uint8Array(buffer);
        let text;
        if (isGzip(bytes)) {
            if (typeof DecompressionStream === "undefined") {
                throw new Error("DecompressionStream not supported by this browser");
            }
            let stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
            text = await new Response(stream).text();
        } else {
            text = new TextDecoder("utf-8").decode(bytes);
        }
        return JSON.parse(text);
    }

    /** Bounded exponential backoff in ms: base·2^attempt, at most max. */
    function backoffDelay(attempt, baseMs, maxMs) {
        let delay = baseMs * Math.pow(2, Math.max(0, attempt));
        return Math.min(maxMs, delay);
    }

    /** Manifest segment key of a period id (§2). */
    function segmentKey(view, id) {
        return view === "year" ? "all" : id.substring(0, 4);
    }

    function joinUrl(base, file) {
        if (!base) {
            return file;
        }
        return base.replace(/\/+$/, "") + "/" + file.replace(/^\/+/, "");
    }

    /**
     * options: {base, fetchFn, nowMs, maxEntries, zone, weekStart}
     */
    function createStore(options) {
        const fetchFn = options.fetchFn || (typeof fetch !== "undefined" ? fetch.bind(null) : null);
        const nowMs = options.nowMs || function () { return Date.now(); };
        const immutable = new LRU(options.maxEntries || 100);
        const mutable = new Map();          // file -> {rev, data}
        const retained = new LRU(8);        // "view|id" -> last running calendar data
        const inflight = new Map();         // url -> Promise
        const segments = {};                // view -> {key -> {rev, entries}}
        const store = {
            base: options.base || "",
            zone: options.zone || "local",
            weekStart: options.weekStart === undefined ? 6 : Number(options.weekStart),
            current: null,                  // parsed current.json
            manifest: null,                 // parsed manifest.json
            requests: 0,
        };

        function once(url, loader) {
            if (inflight.has(url)) {
                return inflight.get(url);
            }
            let promise = loader().finally(function () {
                inflight.delete(url);
            });
            inflight.set(url, promise);
            return promise;
        }

        function fetchBody(url, plainJson) {
            return once(url, async function () {
                store.requests++;
                let response = await fetchFn(url, {cache: plainJson ? "no-cache" : "default"});
                if (!response.ok) {
                    throw new HttpError(response.status, url);
                }
                let buffer = await response.arrayBuffer();
                return decodeBody(buffer);
            });
        }

        function url(file, query) {
            return joinUrl(store.base, file) + (query ? "?" + query : "");
        }

        /** current.json, always revalidated (mutable). */
        store.fetchCurrent = async function () {
            let data = await fetchBody(url("current.json", "t=" + nowMs()), true);
            store.current = data;
            return data;
        };

        /** manifest.json plus every changed segment of `view` (all views if omitted). */
        store.fetchManifest = async function (view) {
            let index = await fetchBody(url("manifest.json", "t=" + nowMs()), true);
            store.manifest = index;
            let views = view ? [view] : core.PERIOD_VIEWS;
            let jobs = [];
            for (let v of views) {
                let wanted = (index.segments && index.segments[v]) || {};
                let known = segments[v] || (segments[v] = {});
                for (let key of Object.keys(known)) {
                    if (wanted[key] === undefined) {
                        delete known[key];
                    }
                }
                for (let key of Object.keys(wanted)) {
                    let rev = wanted[key];
                    if (known[key] !== undefined && known[key].rev === rev) {
                        continue;
                    }
                    jobs.push(fetchBody(url("manifest/" + v + "/" + key + ".json", "r=" + rev), true).then(function (segment) {
                        known[key] = {rev: rev, entries: segment.entries || {}};
                    }));
                }
            }
            await Promise.all(jobs);
            return index;
        };

        store.hasManifest = function () {
            return store.manifest !== null;
        };

        /** Running calendar period id of `view` according to current.json (null if unknown). */
        store.currentPeriodId = function (view) {
            let entry = store.current && store.current.current ? store.current.current[view] : undefined;
            return entry ? entry.period_id : null;
        };

        store.currentEntry = function (view) {
            return store.current && store.current.current ? store.current.current[view] || null : null;
        };

        store.rollingEntry = function (view) {
            return store.current && store.current.rolling ? store.current.rolling[view] || null : null;
        };

        /** Manifest entry or a derived one: {s, rev?, file?, missing?}. */
        store.entry = function (view, id) {
            let segment = segments[view] ? segments[view][segmentKey(view, id)] : undefined;
            if (segment !== undefined && segment.entries[id] !== undefined) {
                return segment.entries[id];
            }
            let manifest = store.manifest;
            if (manifest === null) {
                return null;
            }
            let archive = manifest.archive || {};
            if (archive.first === null || archive.first === undefined) {
                return {s: "nodata"};
            }
            let first = core.periodIdAt(view, (archive.first - 1) * 1000, store.zone, store.weekStart);
            if (core.compareIds(id, first) < 0) {
                return {s: "nodata"};
            }
            return {s: "pending"};   // completed period without entry yet (§5.2)
        };

        store.isSelectable = function (view, id) {
            if (id === store.currentPeriodId(view)) {
                return true;
            }
            let entry = store.entry(view, id);
            return entry !== null && LOADABLE[entry.s] === true;
        };

        /** First period that can contain archive data. */
        store.firstId = function (view) {
            let archive = store.manifest ? store.manifest.archive || {} : {};
            if (archive.first === null || archive.first === undefined) {
                return null;
            }
            return core.periodIdAt(view, (archive.first - 1) * 1000, store.zone, store.weekStart);
        };

        /** Newest loadable completed id of `view` from the loaded segments. */
        store.newestId = function (view) {
            let best = null;
            for (let segment of Object.values(segments[view] || {})) {
                for (let id of Object.keys(segment.entries)) {
                    if (LOADABLE[segment.entries[id].s] && (best === null || id > best)) {
                        best = id;
                    }
                }
            }
            return best;
        };

        /** Immutable completed file (LRU, key = path + rev). */
        store.loadHistoric = async function (file, rev) {
            let key = file + "?r=" + rev;
            let cached = immutable.get(key);
            if (cached !== undefined) {
                return cached;
            }
            let data = await fetchBody(url(file, "r=" + rev), false);
            immutable.set(key, data);
            return data;
        };

        /** Mutable current/rolling file, reloaded only when its rev changed. */
        store.loadMutable = async function (file, rev) {
            let cached = mutable.get(file);
            if (cached !== undefined && cached.rev === rev) {
                return cached.data;
            }
            let data = await fetchBody(url(file, "r=" + rev), false);
            mutable.set(file, {rev: rev, data: data});
            if (data && data.kind === "calendar" && data.period_id) {
                retained.set(data.period + "|" + data.period_id, data);
            }
            return data;
        };

        /** Last loaded running version of the calendar period `id` (kept after a period change,
         *  until the completed file is published). */
        store.lastMutable = function (view, id) {
            let data = retained.get(view + "|" + id);
            return data === undefined ? null : data;
        };

        store.cacheSize = function () {
            return immutable.size;
        };

        /**
         * Data source of a selection:
         * {kind: "mutable", file, rev, refresh, generated} – rolling window / running period,
         * {kind: "historic", file, rev, state, missing} – completed file,
         * {kind: "retained", data} – completed period whose final file is not published yet,
         * {kind: "status", status} – pending | nodata | error | incompatible | unknown.
         */
        store.source = function (view, id, rolling) {
            if (rolling) {
                let entry = store.rollingEntry(view);
                if (entry === null) {
                    return {kind: "status", status: "unknown"};   // not generated (yet) by the report
                }
                return {kind: "mutable", file: entry.file, rev: entry.rev, refresh: entry.refresh, generated: entry.generated};
            }
            let running = store.currentEntry(view);
            if (running !== null && running.period_id === id) {
                return {kind: "mutable", file: running.file, rev: running.rev, refresh: running.refresh, generated: running.generated};
            }
            let entry = store.entry(view, id);
            if (entry !== null && LOADABLE[entry.s] === true) {
                return {kind: "historic", file: entry.file, rev: entry.rev, state: entry.s, missing: entry.missing || []};
            }
            let kept = store.lastMutable(view, id);
            if (kept !== null && (entry === null || entry.s === "pending")) {
                return {kind: "retained", data: kept};
            }
            if (entry === null) {
                return {kind: "status", status: "unknown"};
            }
            return {kind: "status", status: entry.s};
        };

        return store;
    }

    return {
        LRU: LRU,
        HttpError: HttpError,
        isGzip: isGzip,
        decodeBody: decodeBody,
        backoffDelay: backoffDelay,
        segmentKey: segmentKey,
        joinUrl: joinUrl,
        createStore: createStore,
    };
}));
