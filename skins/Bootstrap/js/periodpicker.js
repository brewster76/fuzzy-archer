/*
 * Period picker (E14): small calendar without extra dependency. Day: month grid of days; week: month
 * grid whose rows are weeks (aligned to week_start); month: 12 months of a year; year: pages of 12
 * years. Cells carry the manifest state (§5): ok / gaps are selectable, pending / nodata / error /
 * incompatible / future are disabled with a label. The running period is always selectable.
 * Selecting a period switches week/month/year from the rolling window to the calendar period.
 *
 * Pure part: PeriodPicker.model(view, cursor, ctx) (node-testable). The DOM part only runs in the
 * browser together with PeriodViews / PeriodData.
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory;
    } else {
        // PeriodViews / PeriodData are top-level `const`s (no window properties)
        root.PeriodPicker = factory(root.PeriodCore, root.luxon, root,
            typeof PeriodViews !== "undefined" ? PeriodViews : undefined,
            typeof PeriodData !== "undefined" ? PeriodData : undefined);
    }
}(typeof self !== "undefined" ? self : this, function (core, luxon, root, periodViews, periodData) {
    "use strict";
    const DateTime = luxon.DateTime;
    const LOADABLE = {ok: true, gaps: true};
    const YEARS_PER_PAGE = 12;
    const STATE_TEXT = {
        gaps: "Incomplete data",
        pending: "Data not yet available",
        nodata: "No data available",
        error: "Generation failed",
        incompatible: "Regeneration required",
        unknown: "Data not yet available",
    };

    /**
     * State of one period id: running | future | ok | gaps | pending | nodata | error | incompatible | unknown.
     * ctx.entry(view, id) -> manifest entry {s} or derived entry or null (manifest not loaded).
     */
    function cellState(view, id, ctx) {
        let current = ctx.currentId(view);
        if (current !== null && id === current) {
            return "running";
        }
        if (current !== null && core.compareIds(id, current) > 0) {
            return "future";
        }
        let first = ctx.firstId(view);
        if (first !== null && core.compareIds(id, first) < 0) {
            return "nodata";
        }
        let entry = ctx.entry(view, id);
        return entry && entry.s ? entry.s : "unknown";
    }

    function cell(view, id, ctx) {
        let state = cellState(view, id, ctx);
        return {
            id: id,
            state: state,
            selectable: state === "running" || LOADABLE[state] === true,
            selected: ctx.selectedId === id,
        };
    }

    /** Cursor for the picker of `view` showing `id` (day/week: yyyyMM, month: yyyy, year: last year of page). */
    function cursorFor(view, id, ctx) {
        if (view === "day" || view === "week") {
            // a week is shown in the month of its first day
            return id.substring(0, 6);
        }
        if (view === "month") {
            return id.substring(0, 4);
        }
        let current = Number((ctx.currentId("year") || id).substring(0, 4));
        let year = Number(id.substring(0, 4));
        let pagesBack = Math.max(0, Math.ceil((current - year - (YEARS_PER_PAGE - 1)) / YEARS_PER_PAGE));
        return String(current - pagesBack * YEARS_PER_PAGE);
    }

    function shiftCursor(view, cursor, delta, zone) {
        if (view === "day" || view === "week") {
            return core.shiftId("month", cursor, delta, zone);
        }
        if (view === "month") {
            return String(Number(cursor) + delta);
        }
        return String(Number(cursor) + delta * YEARS_PER_PAGE);
    }

    /** Lowest / highest cursor allowed (null = unlimited). */
    function cursorBounds(view, ctx) {
        let current = ctx.currentId(view);
        let first = ctx.firstId(view);
        let toCursor = function (id) {
            if (id === null) {
                return null;
            }
            if (view === "year") {
                return id;
            }
            return view === "month" ? id.substring(0, 4) : id.substring(0, 6);
        };
        return {min: toCursor(first), max: toCursor(current)};
    }

    function weekdayOrder(weekStart) {
        let order = [];
        for (let i = 0; i < 7; i++) {
            order.push((Number(weekStart) + i) % 7);   // 0 = Monday
        }
        return order;
    }

    function monthGrid(view, cursor, ctx) {
        let monthStart = core.periodStart("month", cursor, ctx.zone);
        let monthEnd = monthStart.plus({months: 1});
        let weekId = core.periodIdAt("week", monthStart.toMillis(), ctx.zone, ctx.weekStart);
        let rows = [];
        while (true) {
            let start = core.periodStart("day", weekId, ctx.zone);
            if (start >= monthEnd) {
                break;
            }
            let cells = [];
            for (let i = 0; i < 7; i++) {
                let dt = start.plus({days: i});
                let id = dt.toFormat("yyyyMMdd");
                let c = view === "day" ? cell("day", id, ctx) : {id: id};
                c.day = dt.day;
                c.inMonth = dt.month === monthStart.month;
                cells.push(c);
            }
            let row = {weekId: weekId, cells: cells};
            if (view === "week") {
                Object.assign(row, cell("week", weekId, ctx));
                row.id = weekId;
            }
            rows.push(row);
            weekId = core.shiftId("day", weekId, 7, ctx.zone);
        }
        return {
            kind: "days",
            year: monthStart.year,
            month: monthStart.month,
            weekdays: weekdayOrder(ctx.weekStart),
            rows: rows,
        };
    }

    /** Complete picker model for `view` at `cursor`. */
    function model(view, cursor, ctx) {
        let result;
        if (view === "day" || view === "week") {
            result = monthGrid(view, cursor, ctx);
        } else if (view === "month") {
            let cells = [];
            for (let m = 1; m <= 12; m++) {
                let c = cell("month", cursor + String(m).padStart(2, "0"), ctx);
                c.month = m;
                cells.push(c);
            }
            result = {kind: "months", year: Number(cursor), cells: cells};
        } else {
            let last = Number(cursor);
            let cells = [];
            for (let y = last - YEARS_PER_PAGE + 1; y <= last; y++) {
                let c = cell("year", String(y), ctx);
                c.year = y;
                cells.push(c);
            }
            result = {kind: "years", from: last - YEARS_PER_PAGE + 1, to: last, cells: cells};
        }
        let bounds = cursorBounds(view, ctx);
        let prev = shiftCursor(view, cursor, -1, ctx.zone);
        let next = shiftCursor(view, cursor, 1, ctx.zone);
        if (view === "year") {
            // a page is reachable while it contains a year >= first year
            result.prev = bounds.min === null || Number(cursor) - YEARS_PER_PAGE >= Number(bounds.min) ? prev : null;
        } else {
            result.prev = bounds.min === null || core.compareIds(prev, bounds.min) >= 0 ? prev : null;
        }
        result.next = bounds.max === null || core.compareIds(next, bounds.max) <= 0 ? next : null;
        result.view = view;
        result.cursor = cursor;
        return result;
    }

    const api = {
        STATE_TEXT: STATE_TEXT,
        cellState: cellState,
        cursorFor: cursorFor,
        shiftCursor: shiftCursor,
        weekdayOrder: weekdayOrder,
        model: model,
    };

    if (root === undefined || typeof root.document === "undefined" || periodViews === undefined) {
        return api;
    }

    // ------------------------------------------------------------------------------------------
    // Browser UI
    const document = root.document;
    const views = periodViews;
    let panel = null;
    let button = null;
    let open = null;   // {view, cursor}

    function titles() {
        return views.ctx.titles || {};
    }

    function locale() {
        return typeof jsLocale !== "undefined" ? jsLocale : undefined;   // global `let`
    }

    function monthName(month, long) {
        let list = long ? titles().month_names : titles().month_abbr;
        if (Array.isArray(list) && list[month - 1]) {
            return list[month - 1];
        }
        return luxon.Info.months(long ? "long" : "short", {locale: locale()})[month - 1];
    }

    function weekdayName(index) {
        let list = titles().day_abbr;
        if (Array.isArray(list) && list[index]) {
            return list[index];
        }
        return luxon.Info.weekdays("short", {locale: locale()})[index];
    }

    function store() {
        return periodData && typeof periodData.store === "function" ? periodData.store() : null;
    }

    function context() {
        let s = store();
        let backfill = s && s.manifest && s.manifest.backfill ? s.manifest.backfill.state : null;
        return {
            zone: views.ctx.zone,
            weekStart: views.ctx.weekStart,
            selectedId: views.state.rolling ? null : views.state.id,
            currentId: function (view) { return views.currentId(view); },
            firstId: function (view) { return s ? s.firstId(view) : null; },
            entry: function (view, id) { return s ? s.entry(view, id) : null; },
            backfillRunning: backfill === "running",
        };
    }

    function stateLabel(state, ctx) {
        if (state === "pending" && ctx.backfillRunning) {
            return views.text("History is being built");
        }
        if (state === "running") {
            return views.text("provisional");
        }
        return STATE_TEXT[state] ? views.text(STATE_TEXT[state]) : "";
    }

    function element(tag, className, text) {
        let el = document.createElement(tag);
        if (className) {
            el.className = className;
        }
        if (text !== undefined) {
            el.textContent = text;
        }
        return el;
    }

    function cellButton(c, text, ctx, extraClass) {
        let b = element("button", "btn btn-sm periodPickCell periodState-" + c.state + (extraClass ? " " + extraClass : ""), text);
        b.type = "button";
        b.classList.add(c.selected ? "btn-primary" : "btn-light");
        b.disabled = !c.selectable;
        let label = stateLabel(c.state, ctx);
        if (label) {
            b.title = label;
        }
        if (c.selected) {
            b.setAttribute("aria-current", "true");
        }
        b.setAttribute("data-id", c.id);
        return b;
    }

    function header(m) {
        let bar = element("div", "d-flex align-items-center justify-content-between mb-1");
        let prev = element("button", "btn btn-sm btn-light periodPickPrev");
        prev.type = "button";
        prev.innerHTML = "<i class=\"bi bi-chevron-left\"></i>";
        prev.setAttribute("aria-label", views.text("Previous period"));
        prev.disabled = m.prev === null;
        prev.addEventListener("click", function () { show(m.view, m.prev, ".periodPickPrev"); });
        let next = element("button", "btn btn-sm btn-light periodPickNext");
        next.type = "button";
        next.innerHTML = "<i class=\"bi bi-chevron-right\"></i>";
        next.setAttribute("aria-label", views.text("Next period"));
        next.disabled = m.next === null;
        next.addEventListener("click", function () { show(m.view, m.next, ".periodPickNext"); });
        let title;
        if (m.kind === "days") {
            title = monthName(m.month, true) + " " + m.year;
        } else if (m.kind === "months") {
            title = String(m.year);
        } else {
            title = m.from + "\u2013" + m.to;
        }
        bar.appendChild(prev);
        bar.appendChild(element("strong", "periodPickTitle", title));
        bar.appendChild(next);
        return bar;
    }

    function render(m) {
        let ctx = context();
        panel.textContent = "";
        panel.appendChild(header(m));
        let states = {};
        let grid;
        if (m.kind === "days") {
            grid = element("div", "periodPickGrid periodPickDays" + (m.view === "week" ? " periodPickWeeks" : ""));
            for (let index of m.weekdays) {
                grid.appendChild(element("div", "periodPickWeekday small text-muted", weekdayName(index)));
            }
            for (let row of m.rows) {
                if (m.view === "week") {
                    let b = cellButton(row, "", ctx, "periodPickWeek");
                    for (let c of row.cells) {
                        b.appendChild(element("span", c.inMonth ? "" : "text-muted", String(c.day)));
                    }
                    grid.appendChild(b);
                    states[row.state] = true;
                } else {
                    for (let c of row.cells) {
                        let b = cellButton(c, String(c.day), ctx, c.inMonth ? "" : "periodPickOutside");
                        grid.appendChild(b);
                        if (c.inMonth) {
                            states[c.state] = true;
                        }
                    }
                }
            }
        } else {
            grid = element("div", "periodPickGrid periodPickCells");
            for (let c of m.cells) {
                let text = m.kind === "months" ? monthName(c.month, false) : String(c.year);
                grid.appendChild(cellButton(c, text, ctx));
                states[c.state] = true;
            }
        }
        grid.addEventListener("click", function (event) {
            let target = event.target.closest("button[data-id]");
            if (target !== null && !target.disabled) {
                select(m.view, target.getAttribute("data-id"));
            }
        });
        panel.appendChild(grid);
        let legend = element("div", "periodPickLegend small mt-1");
        for (let state of ["gaps", "pending", "error", "incompatible", "nodata"]) {
            if (states[state]) {
                let item = element("span", "periodPickLegendItem me-2");
                item.appendChild(element("span", "periodPickSwatch periodState-" + state));
                item.appendChild(document.createTextNode(stateLabel(state, ctx)));
                legend.appendChild(item);
            }
        }
        if (legend.childNodes.length > 0) {
            panel.appendChild(legend);
        }
    }

    function show(view, cursor, focusSelector) {
        open = {view: view, cursor: cursor};
        let m = model(view, cursor, context());
        render(m);
        let focus = focusSelector ? panel.querySelector(focusSelector + ":not([disabled])") : null;
        if (focus === null) {
            focus = panel.querySelector("button[aria-current]") || panel.querySelector(".periodPickGrid button:not([disabled])")
                || panel.querySelector("button:not([disabled])");
        }
        if (focus !== null) {
            focus.focus();
        }
        loadSegments(m, focusSelector);
    }

    /** Lazily loads the manifest segments of the shown cells, then re-renders the same page. */
    function loadSegments(m, focusSelector) {
        let s = store();
        if (s === null || s.manifest === null || typeof s.ensureSegments !== "function") {
            return;
        }
        let ids = [];
        for (let row of m.rows || []) {
            ids.push(row.id || row.weekId);
            for (let c of row.cells) {
                ids.push(c.id);
            }
        }
        for (let c of m.cells || []) {
            ids.push(c.id);
        }
        let keys = s.missingSegments(m.view, s.segmentKeysFor(m.view, ids));
        if (keys.length === 0) {
            return;
        }
        s.ensureSegments(m.view, keys).then(function () {
            if (open !== null && open.view === m.view && open.cursor === m.cursor) {
                show(m.view, m.cursor, focusSelector);
            }
        });
    }

    function openPicker() {
        let view = views.state.view;
        if (!core.isPeriodView(view) || panel === null) {
            return;
        }
        let id = views.state.rolling || !views.state.id ? views.currentId(view) : views.state.id;
        panel.classList.remove("d-none");
        button.setAttribute("aria-expanded", "true");
        show(view, cursorFor(view, id, context()));
    }

    function closePicker(returnFocus) {
        if (panel === null || open === null) {
            return;
        }
        open = null;
        panel.classList.add("d-none");
        button.setAttribute("aria-expanded", "false");
        if (returnFocus) {
            button.focus();
        }
    }

    function select(view, id) {
        closePicker(true);
        views.navigate(view, id);
    }

    function init() {
        button = document.getElementById("periodPicker");
        let toolbar = document.getElementById("periodToolbar") || (button ? button.parentNode : null);
        if (button === null || toolbar === null) {
            return;
        }
        panel = element("div", "dropdown-menu show p-2 periodPickerPanel d-none");
        panel.id = "periodPickerPanel";
        panel.setAttribute("role", "dialog");
        panel.setAttribute("aria-label", views.text("Select period"));
        toolbar.classList.add("position-relative");
        toolbar.appendChild(panel);
        // clicks inside must not reach the outside-click handler (re-rendered targets are detached)
        panel.addEventListener("click", function (event) { event.stopPropagation(); });
        button.setAttribute("aria-haspopup", "dialog");
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-controls", panel.id);
        button.addEventListener("click", function (event) {
            event.stopPropagation();
            if (open !== null) {
                closePicker(false);
            } else {
                openPicker();
            }
        });
        document.addEventListener("click", function () {
            if (open !== null) {
                closePicker(false);
            }
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && open !== null) {
                closePicker(true);
            }
        });
        // route changes (tabs, prev/next, back button) close the picker
        root.addEventListener("hashchange", function () { closePicker(false); });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    api.open = openPicker;
    api.close = closePicker;
    api.isOpen = function () { return open !== null; };
    return api;
}));
