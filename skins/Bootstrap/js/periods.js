/*
 * Period views controller: tabs, hash routing (#day/20261118, #week, #week/20261115, #month/202611,
 * #year/2026; Live = no hash), per-view selection memory and request tokens against stale results.
 * Live! (site.js / charts.js / gauges.js) is not modified; its charts are only resized when its
 * container becomes visible again.
 */
const PeriodViews = (function () {
    "use strict";
    const core = PeriodCore;

    const state = {
        view: "live",
        rolling: false,
        id: null,
        key: null,
        token: 0,
        selection: {},   // view -> {id, rolling}; remembered while the page is open
    };
    const ctx = {
        ready: false,
        zone: "local",
        weekStart: 6,
        titles: null,
        config: null,
        chartsConfig: null,
        nowMs: function () { return Date.now(); },
    };
    // Extension points for the data / chart / picker modules.
    const hooks = {
        prepare: null,                         // function(ctx) -> Promise, before the first route
        renderers: [],                         // function(routeState, token)
        isSelectable: {},                      // view -> function(id) -> bool
        firstId: {},                           // view -> function() -> id | null
        defaultDayId: null,                    // function() -> id | null
    };
    let texts = {};
    let elements = {};

    function text(key, fallback) {
        return texts[key] !== undefined ? texts[key] : (fallback !== undefined ? fallback : key);
    }

    function readTexts() {
        let template = document.getElementById("periodTexts");
        if (template === null) {
            return;
        }
        let root = template.content !== undefined ? template.content : template;
        for (let span of root.querySelectorAll("[data-key]")) {
            texts[span.getAttribute("data-key")] = span.textContent;
        }
    }

    function currentId(view) {
        return core.periodIdAt(view, ctx.nowMs(), ctx.zone, ctx.weekStart);
    }

    function isCurrent(token) {
        return token === state.token;
    }

    function routeContext() {
        return {
            nowMs: ctx.nowMs(),
            zone: ctx.zone,
            weekStart: ctx.weekStart,
            defaultDayId: hooks.defaultDayId ? hooks.defaultDayId() : null,
        };
    }

    /** Navigates (adds a history entry). id null = rolling (week/month/year) / default (day). */
    function navigate(view, id) {
        let hash = core.formatHash(view, id);
        if (view === "live") {
            if (location.hash !== "") {
                history.pushState(null, "", location.pathname + location.search);
            }
            route(true);
            return;
        }
        if (location.hash === hash) {
            route(true);
        } else {
            location.hash = hash;   // triggers hashchange -> route()
        }
    }

    /** Activates a tab with its remembered selection. */
    function activateTab(view) {
        if (view === "live" || !core.isPeriodView(view)) {
            navigate("live", null);
            return;
        }
        let remembered = state.selection[view];
        navigate(view, remembered && !remembered.rolling ? remembered.id : null);
    }

    function route(force) {
        let parsed = core.parseHash(location.hash);
        if (!ctx.ready && parsed !== null && parsed.view !== "live") {
            // weewxData not loaded yet: show the period container while waiting
            applyView(parsed.view);
            setStatus("loading");
            return;
        }
        let resolved = core.resolveRoute(parsed, routeContext());
        if (resolved.replace) {
            let hash = core.formatHash(resolved.view, resolved.id);
            history.replaceState(null, "", location.pathname + location.search + hash);
        }
        let key = resolved.view + "|" + resolved.id + "|" + resolved.rolling;
        if (force !== true && key === state.key) {
            return;   // same route (popstate and hashchange both fired)
        }
        state.key = key;
        state.token++;
        state.view = resolved.view;
        state.id = resolved.id;
        state.rolling = resolved.rolling;
        if (core.isPeriodView(resolved.view)) {
            state.selection[resolved.view] = {id: resolved.id, rolling: resolved.rolling};
        }
        applyView(resolved.view);
        if (core.isPeriodView(resolved.view)) {
            renderPeriod();
        }
    }

    function applyView(view) {
        for (let link of elements.tabs) {
            let active = link.getAttribute("data-view") === view;
            link.classList.toggle("btn-primary", active);
            link.classList.toggle("primaryLive", active);
            link.classList.toggle("btn-light", !active);
            link.classList.toggle("primaryLight", !active);
            if (active) {
                link.setAttribute("aria-current", "page");
            } else {
                link.removeAttribute("aria-current");
            }
        }
        let live = view === "live";
        let wasHidden = elements.live !== null && elements.live.classList.contains("d-none");
        if (elements.live !== null) {
            elements.live.classList.toggle("d-none", !live);
        }
        if (elements.period !== null) {
            elements.period.classList.toggle("d-none", live);
            elements.period.setAttribute("data-view", live ? "" : view);
        }
        if (live && wasHidden) {
            resizeLiveCharts();
        }
    }

    function resizeLiveCharts() {
        if (typeof charts === "undefined") {
            return;
        }
        for (let id of Object.keys(charts)) {
            if (charts[id] !== undefined && charts[id] !== null && typeof charts[id].resize === "function") {
                charts[id].resize();
            }
        }
    }

    function selectableFn(view) {
        return hooks.isSelectable[view];
    }

    function firstIdOf(view) {
        return hooks.firstId[view] ? hooks.firstId[view]() : null;
    }

    /** Target of the previous/next button or null (disabled). */
    function neighbour(step) {
        let view = state.view;
        if (!core.isPeriodView(view)) {
            return null;
        }
        let running = currentId(view);
        if (state.rolling) {
            // From the rolling window, "previous" opens the running calendar period.
            return step < 0 ? running : null;
        }
        return core.neighbourId(view, state.id, step, ctx.zone, running, firstIdOf(view), selectableFn(view));
    }

    function updateToolbar() {
        let view = state.view;
        let rollingView = core.hasRolling(view);
        let prev = neighbour(-1);
        let next = neighbour(1);
        setButton(elements.prev, true, prev !== null);
        setButton(elements.next, true, next !== null);
        setButton(elements.current, rollingView, rollingView && !state.rolling);
        let today = currentId("day");
        let todaySelectable = !selectableFn("day") || selectableFn("day")(today) || today === state.id;
        setButton(elements.today, view === "day", view === "day" && state.id !== today && todaySelectable);
        if (elements.rollingBadge !== null) {
            elements.rollingBadge.classList.toggle("d-none", !state.rolling);
        }
    }

    function setButton(button, visible, enabled) {
        if (button === null) {
            return;
        }
        button.classList.toggle("d-none", !visible);
        button.disabled = !enabled;
    }

    /** Sets the view title. Called by the data module with the actual span of loaded files. */
    function setTitle(title) {
        if (elements.title !== null) {
            elements.title.textContent = title;
        }
    }

    function defaultTitle() {
        if (state.rolling) {
            let window = core.rollingWindow(state.view, ctx.nowMs());
            return core.rollingTitle(window.start, window.end, ctx.zone, ctx.titles);
        }
        return core.calendarTitle(state.view, state.id, ctx.zone, ctx.titles);
    }

    /** kind: null (hidden) | loading | empty | info | warning | error; key: [Texts] key. */
    function setStatus(kind, key, detail) {
        let status = elements.status;
        if (status === null) {
            return;
        }
        let classes = {loading: "alert-secondary", empty: "alert-light", info: "alert-info", warning: "alert-warning", error: "alert-danger"};
        status.className = "alert py-1 px-2 my-1 periodStatus";
        if (!kind) {
            status.classList.add("d-none");
            status.textContent = "";
            status.removeAttribute("data-kind");
            return;
        }
        status.classList.add(classes[kind] || "alert-light");
        status.setAttribute("data-kind", kind);
        let message = text(key || (kind === "loading" ? "Loading" : "No data available"));
        status.textContent = detail ? message + " " + detail : message;
    }

    function renderPeriod() {
        setTitle(defaultTitle());
        updateToolbar();
        let routeState = {view: state.view, id: state.id, rolling: state.rolling};
        if (ctx.config === null) {
            setStatus("error", "Generation failed");
            return;
        }
        if (hooks.renderers.length === 0) {
            setStatus("loading");
            return;
        }
        for (let renderer of hooks.renderers) {
            renderer(routeState, state.token);
        }
    }

    /** Re-renders the visible period view (e.g. after manifest updates) without a new history entry. */
    function refresh() {
        if (ctx.ready && core.isPeriodView(state.view)) {
            state.token++;
            renderPeriod();
        }
    }

    function buildChartContainers() {
        if (elements.charts === null || ctx.chartsConfig === null) {
            return;
        }
        elements.charts.textContent = "";
        for (let chartId of ctx.chartsConfig.order || []) {
            let div = document.createElement("div");
            div.id = "period_" + chartId + "Chart";
            div.className = "chart periodChart";
            div.setAttribute("data-chart-id", chartId);
            elements.charts.appendChild(div);
        }
    }

    function onTabClick(event) {
        let view = this.getAttribute("data-view");
        event.preventDefault();
        activateTab(view);
        if (window.innerWidth < 768 && elements.menu !== null) {
            elements.menu.scrollIntoView();
        }
    }

    function initElements() {
        let byId = function (id) { return document.getElementById(id); };
        elements = {
            menu: byId("menu"),
            tabs: Array.prototype.slice.call(document.querySelectorAll("#graphMenu a[data-view]")),
            live: byId("liveView"),
            period: byId("periodView"),
            title: byId("periodTitle"),
            rollingBadge: byId("periodRolling"),
            status: byId("periodStatus"),
            charts: byId("periodCharts"),
            prev: byId("periodPrev"),
            next: byId("periodNext"),
            current: byId("periodCurrent"),
            today: byId("periodToday"),
        };
    }

    function bindEvents() {
        for (let link of elements.tabs) {
            link.addEventListener("click", onTabClick);
        }
        window.addEventListener("hashchange", function () { route(false); });
        window.addEventListener("popstate", function () { route(false); });
        if (elements.prev !== null) {
            elements.prev.addEventListener("click", function () {
                let target = neighbour(-1);
                if (target !== null) {
                    navigate(state.view, target);
                }
            });
        }
        if (elements.next !== null) {
            elements.next.addEventListener("click", function () {
                let target = neighbour(1);
                if (target !== null) {
                    navigate(state.view, target);
                }
            });
        }
        if (elements.current !== null) {
            elements.current.addEventListener("click", function () {
                if (core.hasRolling(state.view)) {
                    navigate(state.view, null);
                }
            });
        }
        if (elements.today !== null) {
            elements.today.addEventListener("click", function () {
                if (state.view === "day") {
                    navigate("day", currentId("day"));
                }
            });
        }
    }

    /** Called once weewxData (site.js) is available. */
    function configure(data) {
        ctx.zone = core.zoneName(data && data.config ? data.config.station_timezone : undefined);
        ctx.config = data && data.period_config ? data.period_config : null;
        ctx.chartsConfig = data && data.period_charts ? data.period_charts : null;
        ctx.titles = data && data.period_titles ? data.period_titles : null;
        ctx.weekStart = ctx.config !== null && ctx.config.week_start !== undefined ? Number(ctx.config.week_start) : 6;
        buildChartContainers();
        let finish = function () {
            ctx.ready = true;
            route(true);
        };
        if (typeof hooks.prepare === "function" && ctx.config !== null) {
            Promise.resolve().then(function () { return hooks.prepare(ctx); }).catch(function (err) {
                console.log("period views: initial data load failed", err);
            }).then(finish);
        } else {
            finish();
        }
    }

    function waitForWeewxData() {
        if (typeof weewxData !== "undefined" && weewxData !== undefined && weewxData !== null) {
            configure(weewxData);
        } else {
            setTimeout(waitForWeewxData, 100);
        }
    }

    function init() {
        readTexts();
        initElements();
        if (elements.period === null) {
            return;
        }
        bindEvents();
        route(true);
        waitForWeewxData();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    return {
        state: state,
        ctx: ctx,
        hooks: hooks,
        text: text,
        isCurrent: isCurrent,
        currentId: currentId,
        navigate: navigate,
        activateTab: activateTab,
        refresh: refresh,
        setTitle: setTitle,
        setStatus: setStatus,
        updateToolbar: updateToolbar,
    };
}());
