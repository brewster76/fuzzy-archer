/*
 * Period charts: pure ECharts option building for the Day/Week/Month/Year views
 * (docs/historic-data-contract.md, sections 3 and 6). No DOM access; formatting, unit conversion and
 * ECharts helpers are injected through `env`, so the module is testable with node.
 *
 * env = {
 *   format(value, decimals) -> string, unitString(shown, unitLabel) -> string,
 *   unitLabel(targetUnit) -> string | [singular, plural], targetUnit(group) -> unit,
 *   convert(value, fromUnit, toUnit) -> number, decode(text) -> text, text(key) -> string,
 *   formatInterval(startMs, endMs, resolution) -> string, axisLabel(valueMs) -> string,
 *   clipRect(rect, coordSys) -> rect | undefined
 * }
 */
(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.PeriodChartCore = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    const BASE_COLOR = "#111111";
    const BACKGROUND_COLOR = BASE_COLOR + "0a";
    const NIGHT_MODIFIER = 0x1a;
    const DAY_NIGHT = "__daynight";
    const PROVISIONAL_OPACITY = 0.45;
    const X_MIN_INTERVAL = {day: 3 * 3600000, week: 86400000};

    function boolOption(value, defaultValue) {
        if (value === undefined || value === null || value === "") {
            return defaultValue;
        }
        if (typeof value === "boolean") {
            return value;
        }
        return String(value).trim().toLowerCase() === "true";
    }

    function numberOption(value, defaultValue) {
        if (value === undefined || value === null || value === "") {
            return defaultValue;
        }
        let number = Number(value);
        return Number.isFinite(number) ? number : defaultValue;
    }

    function asList(value) {
        if (value === undefined || value === null || value === "") {
            return [];
        }
        return Array.isArray(value) ? value : String(value).split(",").map(function (s) { return s.trim(); }).filter(Boolean);
    }

    function escapeHtml(text) {
        return String(text).replace(/[&<>"']/g, function (c) {
            return {"&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"}[c];
        });
    }

    function effectiveTarget(env, fromUnit, toUnit) {
        if (!fromUnit || !toUnit || fromUnit === toUnit || typeof env.canConvert !== "function") {
            return toUnit || fromUnit;
        }
        return env.canConvert(fromUnit, toUnit) ? toUnit : fromUnit;
    }

    function convertValue(env, value, fromUnit, toUnit) {
        if (value === null || value === undefined || !Number.isFinite(value)) {
            return null;
        }
        if (!fromUnit || !toUnit || fromUnit === toUnit) {
            return value;
        }
        let converted = env.convert(value, fromUnit, toUnit);
        return Number.isFinite(converted) ? converted : null;
    }

    /** Index of the point p with p.start < t <= p.end in points sorted by start, or -1. */
    function findPoint(points, t) {
        let lo = 0;
        let hi = points.length - 1;
        while (lo <= hi) {
            let mid = (lo + hi) >> 1;
            let p = points[mid];
            if (t <= p.start) {
                hi = mid - 1;
            } else if (t > p.end) {
                lo = mid + 1;
            } else {
                return mid;
            }
        }
        return -1;
    }

    /** Converted statistics of an observation: {name: {value, ms?, unitLabel, decimals}}. */
    function convertStats(env, observation, seriesTarget, seriesGroup) {
        let result = {};
        if (!observation || !observation.stats) {
            return result;
        }
        let statUnits = observation.stat_units || {};
        for (let name of Object.keys(observation.stats)) {
            let raw = observation.stats[name];
            if (raw === null || raw === undefined) {
                continue;
            }
            let unit = observation.unit;
            let group = observation.group;
            if (statUnits[name]) {
                unit = statUnits[name][0];
                group = statUnits[name][1];
            }
            let target = group === seriesGroup && seriesTarget ? seriesTarget : env.targetUnit(group) || unit;
            target = effectiveTarget(env, unit, target);
            let value = Array.isArray(raw) ? raw[0] : raw;
            let converted = convertValue(env, value, unit, target);
            if (converted === null) {
                continue;
            }
            result[name] = {
                value: converted,
                ms: Array.isArray(raw) && raw[1] !== null && raw[1] !== undefined ? raw[1] * 1000 : null,
                unitLabel: env.unitLabel(target),
                group: group,
            };
        }
        return result;
    }

    /**
     * Resolves the series of one chart for one view against a period file.
     * Returns [{id, label, plotType, color, decimals, yAxisIndex, unitLabel, group, resolution,
     *           aggregateType, points: [{start, end, value, provisional}] (ms, converted), stats, options, missing}]
     */
    function prepareSeries(chartConfig, data, view, env) {
        let prepared = [];
        let seriesConfigs = chartConfig && chartConfig.series ? chartConfig.series : {};
        for (let seriesId of Object.keys(seriesConfigs)) {
            let options = seriesConfigs[seriesId];
            let viewConfig = options.views ? options.views[view] : undefined;
            if (!viewConfig) {
                continue;
            }
            let fileSeries = data.series ? data.series[viewConfig.key] : undefined;
            let group = viewConfig.obs_group || (fileSeries ? fileSeries.group : options.obs_group);
            let target = viewConfig.target_unit || env.targetUnit(group) || (fileSeries ? fileSeries.unit : undefined);
            if (fileSeries) {
                target = effectiveTarget(env, fileSeries.unit, target);
            }
            let points = [];
            if (fileSeries && Array.isArray(fileSeries.points)) {
                for (let p of fileSeries.points) {
                    let value = p[2] === null ? null : convertValue(env, p[2], fileSeries.unit, target);
                    points.push({start: p[0] * 1000, end: p[1] * 1000, value: value, provisional: p[3] === 1});
                }
            }
            let plotType = options.plotType || "line";
            prepared.push({
                id: seriesId,
                label: env.decode(options.label || seriesId),
                plotType: plotType,
                color: options.lineColor,
                decimals: numberOption(options.decimals, group === "group_direction" ? 0 : 1),
                yAxisIndex: numberOption(options.yAxisIndex, 0),
                unitLabel: env.unitLabel(target),
                group: group,
                resolution: viewConfig.resolution,
                aggregateType: viewConfig.aggregate_type || null,
                points: points,
                stats: convertStats(env, data.observations ? data.observations[viewConfig.observation] : undefined, target, group),
                options: options,
                missing: fileSeries === undefined,
            });
        }
        return prepared;
    }

    function lineData(points) {
        let result = [];
        let previous = null;
        for (let p of points) {
            if (previous !== null && p.start > previous.end) {
                // archive gap between records / buckets: break the line
                result.push([(previous.end + p.start) / 2, null]);
            }
            result.push([p.end, p.value]);
            previous = p;
        }
        return result;
    }

    function scatterData(series, all) {
        let references = asList(series.options.dataReferences).map(function (id) {
            return all.find(function (s) { return s.id === id; });
        }).filter(Boolean);
        return series.points.map(function (p) {
            let value = p.value;
            for (let reference of references) {
                let index = findPoint(reference.points, p.end);
                let referenced = index < 0 ? null : reference.points[index].value;
                if (referenced === null || referenced === 0) {
                    value = null;
                }
            }
            return [p.end, value];
        });
    }

    function barRenderer(series, env) {
        return function (params, api) {
            let value = api.value(2);
            if (value === null || value === undefined || Number.isNaN(value)) {
                return null;
            }
            let start = api.coord([api.value(0), value]);
            let end = api.coord([api.value(1), 0]);
            let x = Math.min(start[0], end[0]);
            let width = Math.abs(end[0] - start[0]);
            if (width > 3) {
                x += 0.5;
                width -= 1;
            }
            let rect = {x: x, y: Math.min(start[1], end[1]), width: width, height: Math.abs(end[1] - start[1])};
            let shape = typeof env.clipRect === "function" ? env.clipRect(rect, params.coordSys) : rect;
            if (!shape) {
                return null;
            }
            return {
                type: "rect",
                shape: shape,
                style: {fill: series.color, opacity: api.value(3) === 1 ? PROVISIONAL_OPACITY : 1},
            };
        };
    }

    /** Server-side statistics as mark points / mark line (§6, E6). */
    function markers(series, env) {
        let result = {};
        let format = function (value) { return env.format(value, series.decimals); };
        // Raw record extremes are not comparable with summed buckets or vector directions.
        let comparable = series.aggregateType !== "sum" && series.aggregateType !== "vecdir" && series.group !== "group_direction";
        let points = [];
        let wanted = [["max", boolOption(series.options.showMaxMarkPoint, false), "top"],
                      ["min", boolOption(series.options.showMinMarkPoint, false), "bottom"]];
        for (let [name, show, position] of wanted) {
            let stat = series.stats[name];
            if (!show || !comparable || !stat || stat.ms === null) {
                continue;
            }
            points.push({
                coord: [stat.ms, stat.value],
                name: name,
                label: {show: true, position: position, formatter: format(stat.value)},
            });
        }
        if (points.length > 0) {
            result.markPoint = {symbolSize: 0, silent: true, data: points};
        }
        let avg = series.stats.avg;
        if (boolOption(series.options.showAvgMarkLine, false) && comparable && avg) {
            let label = format(avg.value) + env.unitString(format(avg.value), series.unitLabel);
            result.markLine = {
                silent: true,
                symbol: "none",
                data: [{yAxis: avg.value, name: "avg", label: {formatter: label}}],
            };
        }
        return result;
    }

    /** Legend suffix with the period total (sum series) or vector mean direction. */
    function statSuffix(series, env) {
        let stat = null;
        let symbol = "";
        if (series.aggregateType === "sum" && series.stats.sum) {
            stat = series.stats.sum;
            symbol = "\u03a3 ";
        } else if (series.group === "group_direction" && series.stats.vecdir) {
            stat = series.stats.vecdir;
            symbol = "\u00d8 ";
        }
        if (stat === null) {
            return "";
        }
        let decimals = series.group === "group_direction" ? 0 : series.decimals;
        let shown = env.format(stat.value, decimals);
        return " (" + symbol + shown + env.unitString(shown, stat.unitLabel) + ")";
    }

    function echartsSeries(series, all, env, z) {
        let base = {
            id: series.id,
            name: series.label,
            yAxisIndex: series.yAxisIndex,
            z: z,
        };
        if (series.plotType === "bar") {
            return Object.assign(base, {
                type: "custom",
                renderItem: barRenderer(series, env),
                dimensions: ["start", "end", "value", "provisional"],
                encode: {x: [0, 1], y: 2},
                data: series.points.map(function (p) { return [p.start, p.end, p.value, p.provisional ? 1 : 0]; }),
                itemStyle: {color: series.color},
                clip: true,
            }, markers(series, env));
        }
        let symbol = series.options.symbol || (series.plotType === "scatter" ? "circle" : "none");
        let result = Object.assign(base, {
            type: series.plotType === "scatter" ? "scatter" : "line",
            data: series.plotType === "scatter" ? scatterData(series, all) : lineData(series.points),
            symbol: symbol,
            symbolKeepAspect: true,
            itemStyle: {color: series.color},
            clip: true,
        }, markers(series, env));
        let symbolSize = series.options.symbolSize;
        if (symbolSize !== undefined && symbolSize !== "") {
            result.symbolSize = Number.isFinite(Number(symbolSize)) ? Number(symbolSize) : symbolFunction(symbolSize);
        } else if (series.plotType === "scatter") {
            result.symbolSize = 4;
        }
        if (result.type === "line") {
            result.showSymbol = symbol !== "none";
            result.connectNulls = false;
            result.lineStyle = {width: numberOption(series.options.lineWidth, 1), color: series.color};
        }
        return result;
    }

    function symbolFunction(source) {
        try {
            // same semantics as [LiveCharts] symbolSize (function expression)
            let fn = new Function("return " + source)();
            return typeof fn === "function" || Number.isFinite(fn) ? fn : 4;
        } catch (e) {
            return 4;
        }
    }

    function yAxes(prepared, env, chartOptions) {
        let axes = [];
        for (let series of prepared) {
            let index = series.yAxisIndex;
            let axis = axes[index] || (axes[index] = {series: []});
            axis.series.push(series);
        }
        let result = [];
        for (let i = 0; i < axes.length; i++) {
            let axis = axes[i] || {series: []};
            let first = axis.series[0] || {options: {}, decimals: 1};
            let options = first.options;
            let decimals = first.decimals;
            let unit = first.unitLabel;
            let item = {
                name: Array.isArray(unit) && unit.length > 1 ? unit[1] : (unit || ""),
                type: "value",
                alignTicks: true,
                scale: true,
                interval: numberOption(options.interval, undefined),
                minInterval: numberOption(options.minInterval, undefined),
                maxInterval: numberOption(options.maxInterval, undefined),
                splitNumber: numberOption(options.splitNumber, undefined),
                nameTextStyle: {fontWeight: "bold"},
                axisLabel: {
                    fontSize: numberOption(options.labelFontSize, 11),
                    formatter: function (value) {
                        if (Math.abs(value) >= 1000) {
                            return value % 1 === 0 ? value.toFixed() : "";
                        }
                        let scaled = value * Math.pow(10, decimals);
                        return Math.abs(scaled - Math.round(scaled)) > 1e-9 ? "" : env.format(value, decimals);
                    },
                },
            };
            let group = first.group;
            if (group === "group_speed" || group === "group_distance" || group === "group_radiation" || group === "group_rain") {
                item.min = 0;
            }
            if (group === "group_percent") {
                item.min = 0;
                item.max = 100;
            }
            if (group === "group_direction") {
                item.min = 0;
                item.max = 360;
                item.minInterval = 90;
                item.maxInterval = 90;
            }
            let hasBars = axis.series.some(function (s) { return s.plotType === "bar"; });
            let allPositive = axis.series.every(function (s) {
                return s.points.every(function (p) { return p.value === null || p.value >= 0; });
            });
            if (hasBars && allPositive && item.min === undefined) {
                item.min = 0;   // bars grow from zero
            }
            if (options.yAxisMin !== undefined && options.yAxisMin !== "") {
                item.min = numberOption(options.yAxisMin, item.min);
            }
            result.push(item);
        }
        if (result.length === 0) {
            result.push({type: "value", scale: true});
        }
        return result;
    }

    function colorModifier(extent) {
        return Math.round(NIGHT_MODIFIER * Math.max(0, Math.min(1, extent))).toString(16).padStart(2, "0");
    }

    /** Day/night background (E2) from the sun events of the file; day and week views only. */
    function dayNightSeries(sunEvents, axis) {
        let areas = [];
        for (let i = 0; i + 1 < sunEvents.length; i++) {
            let from = sunEvents[i];
            let to = sunEvents[i + 1];
            areas.push([{
                xAxis: from[0] * 1000,
                itemStyle: {
                    color: {
                        type: "linear", x: 0, y: 0, x2: 1, y2: 0, global: false,
                        colorStops: [{offset: 0, color: BASE_COLOR + colorModifier(from[1])},
                                     {offset: 1, color: BASE_COLOR + colorModifier(to[1])}],
                    },
                },
            }, {xAxis: to[0] * 1000}]);
        }
        return {
            id: DAY_NIGHT,
            name: DAY_NIGHT,
            type: "line",
            data: [[axis.startMs, null], [axis.endMs, null]],
            symbol: "none",
            silent: true,
            tooltip: {show: false},
            markArea: {silent: true, data: areas},
            z: 0,
        };
    }

    function tooltipFormatter(prepared, env) {
        return function (params) {
            let list = Array.isArray(params) ? params : [params];
            if (list.length === 0) {
                return "";
            }
            let t = list[0].axisValue !== undefined ? list[0].axisValue : (list[0].value ? list[0].value[0] : undefined);
            if (t === undefined) {
                return "";
            }
            let html = "<table>";
            let lastHeader = null;
            let rows = 0;
            for (let series of prepared) {
                let index = findPoint(series.points, t);
                let point = index < 0 ? null : series.points[index];
                let showNone = boolOption(series.options.showTooltipValueNone, series.plotType === "bar");
                if ((point === null || point.value === null) && !showNone) {
                    continue;
                }
                if (point !== null) {
                    let header = env.formatInterval(point.start, point.end, series.resolution);
                    if (header !== lastHeader) {
                        html += "<tr><td colspan=\"2\" style=\"font-size: x-small;\">" + escapeHtml(header) + "</td></tr>";
                        lastHeader = header;
                    }
                }
                let shown = "-";
                if (point !== null && point.value !== null) {
                    let formatted = env.format(point.value, series.decimals);
                    shown = formatted + env.unitString(formatted, series.unitLabel);
                    if (point.provisional) {
                        shown += " (" + env.text("provisional") + ")";
                    }
                }
                let marker = "<span style=\"display:inline-block;margin-right:4px;border-radius:10px;width:10px;height:10px;background-color:"
                    + escapeHtml(series.color || "#999") + ";\"></span>";
                html += "<tr style=\"font-size: small;\"><td>" + marker + escapeHtml(series.label)
                    + "</td><td style=\"text-align: right; padding-left: 10px; font-weight: bold;\">" + escapeHtml(shown) + "</td></tr>";
                rows++;
            }
            return rows > 0 ? html + "</table>" : "";
        };
    }

    /**
     * Complete ECharts option for one chart.
     * ctx = {view, data, chartConfig, env, legendSelected}
     */
    function buildOption(ctx) {
        let env = ctx.env;
        let data = ctx.data;
        let chartOptions = ctx.chartConfig || {};
        let prepared = prepareSeries(chartOptions, data, ctx.view, env);
        let axisSpan = data.axis || data.period_span;
        let axis = {startMs: axisSpan.start * 1000, endMs: axisSpan.end * 1000};
        let series = [];
        let z = prepared.length + 1;
        let suffixes = {};
        let legend = [];
        for (let s of prepared) {
            series.push(echartsSeries(s, prepared, env, z--));
            suffixes[s.label] = statSuffix(s, env);
            let item = {name: s.label};
            let symbol = s.options.symbol;
            if (symbol !== undefined && symbol !== "none") {
                item.icon = symbol;
            }
            legend.push(item);
        }
        let sunEvents = Array.isArray(data.sun_events) ? data.sun_events : [];
        if ((ctx.view === "day" || ctx.view === "week") && sunEvents.length > 1) {
            series.push(dayNightSeries(sunEvents, axis));
        }
        let option = {
            animation: boolOption(chartOptions.animation, true),
            textStyle: {fontSize: numberOption(chartOptions.fontSize, 10)},
            backgroundColor: BACKGROUND_COLOR,
            color: prepared.map(function (s) { return s.color; }),
            legend: {
                type: "plain",
                top: 10,
                data: legend,
                formatter: function (name) { return name + (suffixes[name] || ""); },
            },
            tooltip: {
                trigger: "axis",
                axisPointer: {type: "line", snap: false},
                show: true,
                confine: true,
                formatter: tooltipFormatter(prepared, env),
            },
            xAxis: {
                type: "time",
                min: axis.startMs,
                max: axis.endMs,
                minInterval: X_MIN_INTERVAL[ctx.view],
                axisLine: {show: false},
                axisTick: {show: false},
                splitLine: {show: true},
                axisLabel: {
                    hideOverlap: true,
                    formatter: env.axisLabel,
                    rich: {day: {fontSize: "10px", fontWeight: "bold"}},
                },
            },
            yAxis: yAxes(prepared, env, chartOptions),
            series: series,
        };
        if (ctx.legendSelected) {
            option.legend.selected = ctx.legendSelected;
        }
        return {option: option, series: prepared};
    }

    return {
        BACKGROUND_COLOR: BACKGROUND_COLOR,
        DAY_NIGHT: DAY_NIGHT,
        boolOption: boolOption,
        numberOption: numberOption,
        escapeHtml: escapeHtml,
        findPoint: findPoint,
        convertStats: convertStats,
        prepareSeries: prepareSeries,
        lineData: lineData,
        scatterData: scatterData,
        barRenderer: barRenderer,
        markers: markers,
        statSuffix: statSuffix,
        yAxes: yAxes,
        dayNightSeries: dayNightSeries,
        tooltipFormatter: tooltipFormatter,
        buildOption: buildOption,
    };
}));
