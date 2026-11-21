"use strict";
const test = require("node:test");
const assert = require("node:assert");
const path = require("node:path");
const cc = require(path.join(__dirname, "..", "..", "skins", "Bootstrap", "js", "periodchartcore.js"));

const env = {
    format: (v, d) => Number(v).toFixed(d),
    unitString: (shown, unit) => (Array.isArray(unit) ? unit[1] : (unit || "")),
    unitLabel: (t) => ({degree_C: "°C", degree_F: "°F", mm: " mm", inch: " in", degree_compass: "°", km_per_hour: " km/h"})[t],
    targetUnit: (g) => ({group_temperature: "degree_C", group_rain: "mm", group_direction: "degree_compass", group_speed: "km_per_hour"})[g],
    convert: (v, from, to) => {
        if (from === "degree_F" && to === "degree_C") return (v - 32) * 5 / 9;
        if (from === "inch" && to === "mm") return v * 25.4;
        if (from === "mile_per_hour" && to === "km_per_hour") return v * 1.609344;
        return v;
    },
    decode: (t) => t,
    text: (k) => k,
    formatInterval: (s, e) => s + "-" + e,
    axisLabel: (v) => String(v),
    clipRect: (r) => r,
};

function file(extra) {
    return Object.assign({
        schema_version: 1, kind: "calendar", period: "day", period_id: "20261118", state: "running",
        period_span: {start: 1000, end: 4600}, axis: {start: 1000, end: 4600},
        observations: {
            "wx/outTemp": {unit: "degree_F", group: "group_temperature", count: 3,
                stats: {min: [32, 1600], max: [50, 2200], avg: 41}},
            "wx/rain": {unit: "inch", group: "group_rain", count: 3, stats: {sum: 1, max: [0.5, 1900]}},
            "wx/wind": {unit: "mile_per_hour", group: "group_speed", count: 3,
                stats: {vecavg: 10, vecdir: 270}, stat_units: {vecdir: ["degree_compass", "group_direction"]}},
        },
        series: {
            "wx/outTemp/none/native": {unit: "degree_F", group: "group_temperature",
                points: [[700, 1000, 32], [1000, 1300, 50], [1900, 2200, null], [2200, 2500, 41, 1]]},
            "wx/rain/sum/PT1H": {unit: "inch", group: "group_rain",
                points: [[0, 3600, 1], [3600, 7200, null, 1]]},
            "wx/wind/vecdir/PT1H": {unit: "degree_compass", group: "group_direction",
                points: [[0, 3600, 270], [3600, 7200, 90, 1]]},
        },
        sun_events: [[1000, 1, "start"], [2000, 0.5, "rising"], [4600, 0, "end"]],
    }, extra || {});
}

function view(key, observation, aggregate, resolution, group, target) {
    return {key: key, observation: observation, aggregate_type: aggregate, resolution: resolution,
        obs_group: group, target_unit: target};
}

const chartConfig = {
    temp: {series: {outTemp: {label: "Temperature", lineColor: "#b44242", decimals: "1",
        showMaxMarkPoint: "true", showMinMarkPoint: "true", showAvgMarkLine: "true",
        views: {day: view("wx/outTemp/none/native", "wx/outTemp", null, "native", "group_temperature", "degree_C")}}}},
    rain: {series: {rain: {label: "Rain", plotType: "bar", decimals: "1", lineColor: "#428bca",
        showMaxMarkPoint: "true",
        views: {day: view("wx/rain/sum/PT1H", "wx/rain", "sum", "PT1H", "group_rain", "mm")}}}},
    dir: {series: {windDir: {label: "Direction", plotType: "scatter", decimals: "0",
        views: {day: view("wx/wind/vecdir/PT1H", "wx/wind", "vecdir", "PT1H", "group_direction", "degree_compass")}}}},
    missing: {series: {foo: {label: "Foo", views: {day: view("wx/foo/none/native", "wx/foo", null, "native", "", "")}}}},
};

test("findPoint uses (start, end] intervals", () => {
    const points = [{start: 0, end: 10}, {start: 10, end: 20}, {start: 30, end: 40}];
    assert.strictEqual(cc.findPoint(points, 0), -1);
    assert.strictEqual(cc.findPoint(points, 10), 0);
    assert.strictEqual(cc.findPoint(points, 10.5), 1);
    assert.strictEqual(cc.findPoint(points, 25), -1);
    assert.strictEqual(cc.findPoint(points, 40), 2);
    assert.strictEqual(cc.findPoint(points, 41), -1);
});

test("prepareSeries converts units, keeps provisional flags and flags missing series", () => {
    const [temp] = cc.prepareSeries(chartConfig.temp, file(), "day", env);
    assert.strictEqual(temp.points[0].start, 700000);
    assert.strictEqual(temp.points[0].value, 0);
    assert.strictEqual(temp.points[1].value, 10);
    assert.strictEqual(temp.points[2].value, null);
    assert.strictEqual(temp.points[3].provisional, true);
    assert.strictEqual(temp.unitLabel, "°C");
    assert.deepStrictEqual(temp.stats.max, {value: 10, ms: 2200000, unitLabel: "°C", group: "group_temperature"});
    assert.ok(Math.abs(temp.stats.avg.value - 5) < 1e-9);
    const [missing] = cc.prepareSeries(chartConfig.missing, file(), "day", env);
    assert.strictEqual(missing.missing, true);
    assert.deepStrictEqual(missing.points, []);
});

test("stat_units are used for statistics with a different unit", () => {
    const [dir] = cc.prepareSeries(chartConfig.dir, file(), "day", env);
    assert.strictEqual(dir.stats.vecdir.value, 270);
    assert.strictEqual(dir.stats.vecdir.unitLabel, "°");
    assert.ok(Math.abs(dir.stats.vecavg.value - 16.09344) < 1e-9);
    assert.strictEqual(cc.statSuffix(dir, env), " (Ø 270°)");
});

test("line data is drawn at bucket end and broken at gaps", () => {
    const [temp] = cc.prepareSeries(chartConfig.temp, file(), "day", env);
    const data = cc.lineData(temp.points);
    assert.deepStrictEqual(data.map((d) => d[0]), [1000000, 1300000, 1600000, 2200000, 2500000]);
    assert.strictEqual(data[2][1], null);
});

test("markers use server statistics; sums get a legend total instead of mark points", () => {
    const [temp] = cc.prepareSeries(chartConfig.temp, file(), "day", env);
    const m = cc.markers(temp, env);
    assert.deepStrictEqual(m.markPoint.data.map((p) => p.coord), [[2200000, 10], [1600000, 0]]);
    assert.ok(Math.abs(m.markLine.data[0].yAxis - 5) < 1e-9);
    const [rain] = cc.prepareSeries(chartConfig.rain, file(), "day", env);
    assert.deepStrictEqual(cc.markers(rain, env), {});
    assert.strictEqual(cc.statSuffix(rain, env), " (Σ 25.4 mm)");
});

test("bars span start..end, are clipped and provisional bars are lighter", () => {
    const [rain] = cc.prepareSeries(chartConfig.rain, file(), "day", env);
    const render = cc.barRenderer(rain, env);
    const values = [0, 3600000, 25.4, 1];
    const api = {value: (i) => values[i], coord: ([x, y]) => [x / 10000, 100 - y]};
    const shape = render({coordSys: {}}, api);
    assert.strictEqual(shape.type, "rect");
    assert.strictEqual(shape.shape.x, 0.5);
    assert.strictEqual(shape.shape.width, 359);
    assert.ok(Math.abs(shape.shape.height - 25.4) < 1e-9);
    assert.ok(shape.style.opacity < 1);
    values[2] = NaN;
    assert.strictEqual(render({coordSys: {}}, api), null);
});

test("buildOption: axis range, day/night only for day/week, tooltip with interval and provisional", () => {
    const built = cc.buildOption({view: "day", data: file(), chartConfig: chartConfig.temp, env: env});
    const option = built.option;
    assert.strictEqual(option.xAxis.min, 1000000);
    assert.strictEqual(option.xAxis.max, 4600000);
    const dayNight = option.series.find((s) => s.id === cc.DAY_NIGHT);
    assert.strictEqual(dayNight.markArea.data.length, 2);
    assert.strictEqual(dayNight.markArea.data[0][0].xAxis, 1000000);
    assert.strictEqual(option.legend.data.length, 1);
    const html = option.tooltip.formatter([{axisValue: 2400000}]);
    assert.match(html, /2200000-2500000/);
    assert.match(html, /5\.0°C \(provisional\)/);
    assert.strictEqual(option.tooltip.formatter([{axisValue: 1700000}]), "");

    const month = file({period: "month"});
    const monthOption = cc.buildOption({view: "month", data: month, chartConfig: chartConfig.temp, env: env}).option;
    assert.strictEqual(monthOption.series.find((s) => s.id === cc.DAY_NIGHT), undefined);
});

test("buildOption: bar charts start at zero, direction axis 0..360, legend selection kept", () => {
    const rain = cc.buildOption({view: "day", data: file(), chartConfig: chartConfig.rain, env: env,
        legendSelected: {Rain: false}}).option;
    assert.strictEqual(rain.series[0].type, "custom");
    assert.deepStrictEqual(rain.series[0].encode, {x: 4, y: 2});
    assert.deepStrictEqual(rain.series[0].data.map((point) => point[4]), [1800000, 5400000]);
    assert.strictEqual(rain.tooltip.axisPointer.snap, true);
    assert.strictEqual(rain.yAxis[0].min, 0);
    assert.deepStrictEqual(rain.legend.selected, {Rain: false});
    assert.strictEqual(rain.legend.formatter("Rain"), "Rain (Σ 25.4 mm)");
    const rainTip = rain.tooltip.formatter([{axisValue: 5000000}]);
    assert.match(rainTip, /Rain.*-/);
    const dir = cc.buildOption({view: "day", data: file(), chartConfig: chartConfig.dir, env: env}).option;
    assert.strictEqual(dir.series[0].type, "scatter");
    assert.strictEqual(dir.yAxis[0].max, 360);
    assert.deepStrictEqual(dir.series[0].data, [[3600000, 270], [7200000, 90]]);
});

test("buildOption: visible max marker expands the value axis beyond averaged yearly points", () => {
    const annual = file({
        period: "year",
        observations: {
            "wx/outTemp": {unit: "degree_C", group: "group_temperature", count: 2,
                stats: {min: [10, 1600], max: [40, 2200], avg: 20}},
        },
        series: {
            "wx/outTemp/avg/P1D": {unit: "degree_C", group: "group_temperature",
                points: [[1000, 2000, 19], [2000, 3000, 21]]},
        },
    });
    const annualConfig = {series: {outTemp: {label: "Temperature", lineColor: "#b44242",
        showMaxMarkPoint: "true",
        views: {year: view("wx/outTemp/avg/P1D", "wx/outTemp", "avg", "P1D", "group_temperature", "degree_C")}}}};
    const option = cc.buildOption({view: "year", data: annual, chartConfig: annualConfig, env: env}).option;
    assert.ok(option.yAxis[0].max > 40);
    assert.strictEqual(option.series[0].markPoint.data[0].coord[1], 40);
});

test("scatter dataReferences null out points whose reference is zero or missing", () => {
    const config = {series: {
        speed: {label: "Speed", views: {day: view("wx/s/none/native", "wx/s", null, "native", "group_speed", "km_per_hour")}},
        dir: {label: "Dir", plotType: "scatter", dataReferences: "speed",
            views: {day: view("wx/d/none/native", "wx/d", null, "native", "group_direction", "degree_compass")}},
    }};
    const data = file({series: {
        "wx/s/none/native": {unit: "km_per_hour", group: "group_speed", points: [[0, 300, 5], [300, 600, 0]]},
        "wx/d/none/native": {unit: "degree_compass", group: "group_direction", points: [[0, 300, 90], [300, 600, 180], [600, 900, 200]]},
    }});
    const prepared = cc.prepareSeries(config, data, "day", env);
    assert.deepStrictEqual(cc.scatterData(prepared[1], prepared), [[300000, 90], [600000, null], [900000, null]]);
});

test("missing unit conversion keeps the database unit and its label", () => {
    const noConv = Object.assign({}, env, {canConvert: (from, to) => !(from === "degree_F" && to === "degree_C")});
    const [temp] = cc.prepareSeries(chartConfig.temp, file(), "day", noConv);
    assert.strictEqual(temp.unitLabel, "°F");
    assert.strictEqual(temp.points[1].value, 50);
    assert.strictEqual(temp.stats.max.value, 50);
    assert.strictEqual(temp.stats.max.unitLabel, "°F");
});

test("escapeHtml and option parsing", () => {
    assert.strictEqual(cc.escapeHtml("<a href='x'>&</a>"), "&lt;a href=&#39;x&#39;&gt;&amp;&lt;/a&gt;");
    assert.strictEqual(cc.boolOption("True", false), true);
    assert.strictEqual(cc.boolOption(undefined, true), true);
    assert.strictEqual(cc.numberOption("x", 3), 3);
    assert.strictEqual(cc.numberOption("2", 3), 2);
});
