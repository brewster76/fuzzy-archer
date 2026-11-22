/*
 * Period views data controller: connects PeriodStore with PeriodViews. Loads current.json and the
 * manifest, resolves the data source of the selection, shows loading / empty / error states,
 * polls mutable data with the generation interval and retries failures with bounded backoff.
 * Chart modules subscribe with PeriodData.subscribe(function (event) {...}):
 *   {type: "clear"}                                       – selection changed, remove old data
 *   {type: "data", data, route, source, changed}          – period file to display
 */
const PeriodData = (function () {
    "use strict";
    const core = PeriodCore;
    const views = PeriodViews;

    const MIN_POLL_MS = 60000;
    const INDEX_MAX_AGE_MS = 60000;
    const BACKOFF_BASE_MS = 5000;
    const BACKOFF_MAX_MS = 600000;

    const listeners = [];
    let store = null;
    let timer = null;
    let attempt = 0;
    let forceIndexes = false;
    let indexFetched = 0;
    let shown = {key: null, data: null};

    function subscribe(listener) {
        listeners.push(listener);
    }

    function emit(event) {
        for (let listener of listeners) {
            try {
                listener(event);
            } catch (err) {
                console.log("period views: listener failed", err);
            }
        }
    }

    function viewRefreshMs(view) {
        let config = views.ctx.config || {};
        let seconds = config.refresh ? Number(config.refresh[view]) : 0;
        if (!seconds) {
            seconds = Number(config.archive_interval) || 300;
        }
        return Math.max(MIN_POLL_MS, seconds * 1000);
    }

    /** Poll delay for a mutable file: shortly after the next expected generation. */
    function mutablePollMs(source, view) {
        let refreshMs = source.refresh ? Math.max(MIN_POLL_MS, source.refresh * 1000) : viewRefreshMs(view);
        if (!source.generated) {
            return refreshMs;
        }
        let due = source.generated * 1000 + refreshMs + 30000 - Date.now();
        return Math.min(refreshMs, Math.max(MIN_POLL_MS, due));
    }

    function schedule(delay, token) {
        clearTimeout(timer);
        timer = setTimeout(function () {
            if (!views.isCurrent(token)) {
                return;
            }
            if (document.hidden) {
                schedule(delay, token);
                return;
            }
            forceIndexes = true;
            views.refresh();
        }, delay);
    }

    async function ensureIndexes(force) {
        let historyEnabled = !views.ctx.config || views.ctx.config.generate_history !== false;
        if (!force && store.current !== null && (!historyEnabled || store.manifest !== null) &&
                Date.now() - indexFetched < INDEX_MAX_AGE_MS) {
            return;
        }
        let requests = [store.fetchCurrent()];
        if (historyEnabled) {
            requests.push(store.fetchManifest());
        }
        let results = await Promise.allSettled(requests);
        indexFetched = Date.now();
        if (results[0].status === "rejected" && store.current === null) {
            throw results[0].reason;
        }
        if (historyEnabled && results[1].status === "rejected" && store.manifest === null) {
            throw results[1].reason;
        }
    }

    function formatTimestamp(seconds) {
        let locale = typeof jsLocale !== "undefined" ? jsLocale : undefined;
        let dt = luxon.DateTime.fromMillis(seconds * 1000, {zone: views.ctx.zone});
        if (locale) {
            dt = dt.setLocale(locale);
        }
        return dt.toLocaleString(luxon.DateTime.DATETIME_SHORT);
    }

    function setDataState(data, provisional) {
        let element = document.getElementById("periodDataState");
        if (element === null) {
            return;
        }
        if (!data || !data.generated) {
            element.textContent = "";
            return;
        }
        let parts = [views.text("Data as of") + ": " + formatTimestamp(data.generated)];
        if (provisional) {
            parts.push(views.text("provisional"));
        }
        element.textContent = parts.join(" \u00b7 ");
    }

    function backfillRunning() {
        return store.manifest !== null && store.manifest.backfill !== undefined && store.manifest.backfill.state === "running";
    }

    function show(data, route, source, token) {
        if (!views.isCurrent(token)) {
            return;
        }
        let changed = data !== shown.data;
        shown.data = data;
        if (route.rolling && data.period_span) {
            views.setTitle(core.rollingTitle(data.period_span.start * 1000, data.period_span.end * 1000, views.ctx.zone, views.ctx.titles));
        }
        let provisional = source.kind === "mutable" || source.kind === "retained";
        setDataState(data, provisional);
        if (data.state === "gaps") {
            views.setStatus("info", "Incomplete data");
        } else if (source.kind === "retained") {
            views.setStatus("info", "Data not yet available");
        } else {
            views.setStatus(null);
        }
        emit({type: "data", data: data, route: route, source: source, changed: changed});
    }

    function showState(status, token) {
        if (!views.isCurrent(token)) {
            return;
        }
        shown.data = null;
        emit({type: "clear"});
        setDataState(null);
        switch (status) {
            case "pending":
                views.setStatus("info", backfillRunning() ? "History is being built" : "Data not yet available");
                break;
            case "error":
                views.setStatus("error", "Generation failed");
                break;
            case "incompatible":
                views.setStatus("warning", "Regeneration required");
                break;
            case "unknown":
                views.setStatus("warning", "Data not yet available");
                break;
            default:
                views.setStatus("empty", "No data available");
        }
    }

    async function render(route, token) {
        clearTimeout(timer);
        let key = route.view + "|" + route.id + "|" + route.rolling;
        if (key !== shown.key) {
            shown = {key: key, data: null};
            emit({type: "clear"});
            setDataState(null);
        }
        let force = forceIndexes;
        forceIndexes = false;
        let loadingTimer = setTimeout(function () {
            if (views.isCurrent(token) && shown.data === null) {
                views.setStatus("loading");
            }
        }, 150);
        try {
            await ensureIndexes(force);
            if (!views.isCurrent(token)) {
                return;
            }
            views.updateToolbar();
            let source = store.source(route.view, route.id, route.rolling);
            if (source.kind === "mutable") {
                let data = await store.loadMutable(source.file, source.rev);
                show(data, route, source, token);
                schedule(mutablePollMs(source, route.view), token);
            } else if (source.kind === "historic") {
                let data = await store.loadHistoric(source.file, source.rev);
                show(data, route, source, token);
                if (backfillRunning()) {
                    schedule(viewRefreshMs(route.view), token);
                }
            } else if (source.kind === "retained") {
                show(source.data, route, source, token);
                schedule(viewRefreshMs(route.view), token);
            } else {
                showState(source.status, token);
                if (source.status === "pending" || source.status === "unknown") {
                    schedule(viewRefreshMs(route.view), token);
                } else if (backfillRunning()) {
                    schedule(viewRefreshMs(route.view), token);
                }
            }
            attempt = 0;
        } catch (err) {
            if (!views.isCurrent(token)) {
                return;
            }
            console.log("period views: load failed", err);
            if (shown.data === null) {
                views.setStatus("warning", "Data not yet available");
            }
            // 404 = not uploaded yet (§5.2), network or decode errors: retry with bounded backoff
            schedule(PeriodStore.backoffDelay(attempt++, BACKOFF_BASE_MS, BACKOFF_MAX_MS), token);
        } finally {
            clearTimeout(loadingTimer);
        }
    }

    function defaultDayId() {
        let today = views.currentId("day");
        let candidates = [store.currentPeriodId("day"), store.newestId("day")].filter(function (id) {
            return id && id <= today;
        });
        candidates.sort();
        return candidates.length > 0 ? candidates[candidates.length - 1] : null;
    }

    async function prepare(ctx) {
        store = PeriodStore.createStore({
            base: ctx.config.data_url || "historic_data",
            zone: ctx.zone,
            weekStart: ctx.weekStart,
        });
        for (let view of core.PERIOD_VIEWS) {
            views.hooks.isSelectable[view] = function (id) { return store.isSelectable(view, id); };
            views.hooks.firstId[view] = function () { return store.firstId(view); };
        }
        views.hooks.defaultDayId = defaultDayId;
        await ensureIndexes(true);
    }

    views.hooks.prepare = prepare;
    views.hooks.renderers.push(render);

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden && core.isPeriodView(views.state.view)) {
            forceIndexes = true;
            views.refresh();
        }
    });

    return {
        subscribe: subscribe,
        store: function () { return store; },
    };
}());
