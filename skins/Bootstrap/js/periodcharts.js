/*
 * Period charts controller: renders the period file emitted by PeriodData into one ECharts instance
 * per [PeriodCharts] chart (containers "period_<chartId>Chart" created by periods.js).
 * Option building lives in periodchartcore.js.
 */
const PeriodCharts = (function () {
    "use strict";
    const views = PeriodViews;
    const chartCore = PeriodChartCore;
    const instances = {};   // chartId -> {chart, data}
    let lastEvent = null;
    let warnedConversions = {};

    function zone() {
        return views.ctx.zone;
    }

    function locale() {
        return typeof jsLocale !== "undefined" ? jsLocale : undefined;
    }

    function dateTime(ms) {
        return luxon.DateTime.fromMillis(ms, {zone: zone(), locale: locale()});
    }

    function isMidnight(d) {
        return d.hour === 0 && d.minute === 0 && d.second === 0;
    }

    /** Tooltip header "(start, end]": date only for whole days, otherwise date + times. */
    function formatInterval(startMs, endMs) {
        let start = dateTime(startMs);
        let end = dateTime(endMs);
        if (isMidnight(start) && isMidnight(end)) {
            let lastDay = end.minus({days: 1});
            let first = start.toLocaleString(luxon.DateTime.DATE_SHORT);
            return lastDay.hasSame(start, "day") ? start.toLocaleString({weekday: "short", day: "numeric", month: "numeric", year: "numeric"})
                : first + " \u2013 " + lastDay.toLocaleString(luxon.DateTime.DATE_SHORT);
        }
        let endText = end.hasSame(start, "day") || (isMidnight(end) && end.minus({days: 1}).hasSame(start, "day"))
            ? end.toLocaleString(luxon.DateTime.TIME_SIMPLE)
            : end.toLocaleString(luxon.DateTime.DATETIME_SHORT);
        return start.toLocaleString(luxon.DateTime.DATETIME_SHORT) + " \u2013 " + endText;
    }

    function axisLabel(view) {
        return function (value) {
            let d = dateTime(value);
            if (view === "year") {
                return d.day === 1 ? "{day|" + d.toFormat("LLL") + "}" : d.toFormat("d");
            }
            if (isMidnight(d)) {
                if (view === "week") {
                    return "{day|" + d.toFormat("ccc d") + "}";
                }
                return d.day === 1 && view === "month" ? "{day|" + d.toFormat("d LLL") + "}" : "{day|" + d.toFormat("d") + "}";
            }
            return d.toLocaleString(luxon.DateTime.TIME_24_SIMPLE);
        };
    }

    function canConvert(fromUnit, toUnit) {
        let key = fromUnit + "_To_" + toUnit;
        if (typeof window[key] === "function") {
            return true;
        }
        if (!warnedConversions[key]) {
            warnedConversions[key] = true;
            console.log("period charts: no unit conversion " + key + ", showing database unit");
        }
        return false;
    }

    function convert(value, fromUnit, toUnit) {
        let fn = window[fromUnit + "_To_" + toUnit];
        return typeof fn === "function" ? fn(value) : value;
    }

    function env(view) {
        let units = typeof weewxData !== "undefined" && weewxData && weewxData.units ? weewxData.units : {Groups: {}, Labels: {}};
        return {
            format: function (value, decimals) { return format(value, decimals); },
            unitString: function (shown, unit) { return getUnitString(shown, unit); },
            unitLabel: function (target) { return target && units.Labels ? units.Labels[target] : undefined; },
            targetUnit: function (group) { return group && units.Groups ? units.Groups[group] : undefined; },
            convert: convert,
            canConvert: canConvert,
            decode: function (text) { return typeof decodeHtml === "function" ? decodeHtml(text) : text; },
            text: function (key) { return views.text(key); },
            formatInterval: formatInterval,
            axisLabel: axisLabel(view),
            clipRect: function (rect, coordSys) { return echarts.graphic.clipRectByRect(rect, coordSys); },
        };
    }

    function container() {
        return document.getElementById("periodCharts");
    }

    function chartIds() {
        let config = views.ctx.chartsConfig;
        return config && Array.isArray(config.order) ? config.order : [];
    }

    function instance(chartId) {
        let entry = instances[chartId];
        if (entry !== undefined && !entry.chart.isDisposed()) {
            return entry;
        }
        let element = document.getElementById("period_" + chartId + "Chart");
        if (element === null) {
            return null;
        }
        let chart = echarts.init(element, null, {locale: typeof eChartsLocale !== "undefined" ? eChartsLocale : undefined});
        entry = {chart: chart, data: null, view: null, visible: false};
        instances[chartId] = entry;
        return entry;
    }

    function legendSelected(chart) {
        let option = chart.getOption();
        if (option && Array.isArray(option.legend) && option.legend[0] && option.legend[0].selected) {
            return option.legend[0].selected;
        }
        return undefined;
    }

    function clear() {
        lastEvent = null;
        for (let chartId of Object.keys(instances)) {
            let entry = instances[chartId];
            if (!entry.chart.isDisposed()) {
                entry.chart.clear();
            }
            entry.data = null;
            entry.visible = false;
        }
        let element = container();
        if (element !== null) {
            element.classList.add("d-none");
        }
    }

    function render(event) {
        lastEvent = event;
        let chartsElement = container();
        if (chartsElement !== null) {
            chartsElement.classList.remove("d-none");
        }
        let view = event.route.view;
        let chartsConfig = views.ctx.chartsConfig;
        let hasVisibleChart = false;
        for (let chartId of chartIds()) {
            let chartElement = document.getElementById("period_" + chartId + "Chart");
            let chartConfig = chartsConfig.charts[chartId];
            if (chartElement === null) {
                continue;
            }
            let entry = instances[chartId];
            try {
                let keepLegend = entry && !entry.chart.isDisposed()
                    && entry.view === view && entry.data !== null
                    ? legendSelected(entry.chart) : undefined;
                let built = chartCore.buildOption({
                    view: view,
                    data: event.data,
                    chartConfig: chartConfig,
                    env: env(view),
                    legendSelected: keepLegend,
                });
                let visible = chartCore.boolOption(chartConfig.showEmpty, false) || chartCore.hasData(built.series);
                chartElement.classList.toggle("d-none", !visible);
                if (!visible) {
                    if (entry && !entry.chart.isDisposed()) {
                        entry.chart.clear();
                        entry.data = event.data;
                        entry.view = view;
                        entry.visible = false;
                    }
                    continue;
                }
                entry = instance(chartId);
                if (entry === null) {
                    continue;
                }
                entry.chart.resize();
                if (event.changed === false && entry.data === event.data && entry.view === view
                        && entry.visible) {
                    hasVisibleChart = true;
                    continue;   // same file object: nothing to redraw
                }
                for (let s of built.series) {
                    if (s.missing) {
                        console.log("period charts: series " + s.id + " of chart " + chartId + " not in period file");
                    }
                }
                entry.chart.setOption(built.option, {notMerge: true});
                entry.data = event.data;
                entry.view = view;
                entry.visible = true;
                hasVisibleChart = true;
            } catch (err) {
                console.log("period charts: could not render chart " + chartId, err);
                chartElement.classList.add("d-none");
                if (entry && !entry.chart.isDisposed()) {
                    entry.chart.clear();
                    entry.data = null;
                    entry.visible = false;
                }
            }
        }
        if (chartsElement !== null) {
            chartsElement.classList.toggle("d-none", !hasVisibleChart);
        }
    }

    function onEvent(event) {
        if (event.type === "clear") {
            clear();
        } else if (event.type === "data") {
            render(event);
        }
    }

    function resize() {
        let period = document.getElementById("periodView");
        if (period === null || period.classList.contains("d-none")) {
            return;
        }
        for (let chartId of Object.keys(instances)) {
            let entry = instances[chartId];
            if (!entry.chart.isDisposed()) {
                entry.chart.resize();
            }
        }
    }

    if (typeof PeriodData !== "undefined") {
        PeriodData.subscribe(onEvent);
    }
    window.addEventListener("resize", resize);

    return {
        instances: instances,
        resize: resize,
        lastEvent: function () { return lastEvent; },
    };
}());
