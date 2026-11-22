"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../../skins/Bootstrap/js/windradarcore.js");

test("assigns compass angles to the nearest eight sectors, including north wraparound", () => {
    assert.deepEqual([0, 45, 90, 135, 180, 225, 270, 315, 360].map(core.sectorIndex),
        [0, 1, 2, 3, 4, 5, 6, 7, 0]);
    assert.equal(core.sectorIndex(22.49), 0);
    assert.equal(core.sectorIndex(22.5), 1);
    assert.deepEqual(core.DIRECTIONS, ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]);
});

test("uses localized eight-point compass labels from WeeWX ordinal translations", () => {
    assert.deepEqual(
        core.compassLabels(["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW", "-"]),
        ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]);
    assert.deepEqual(
        core.compassLabels("N, NNO, NO, ONO, O, OSO, SO, SSO, S, SSW, SW, WSW, W, WNW, NW, NNW, -"),
        ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]);
    assert.deepEqual(core.compassLabels(["Nord", "Nordost", "Ost", "Südost", "Süd", "Südwest", "West", "Nordwest"]),
        ["Nord", "Nordost", "Ost", "Südost", "Süd", "Südwest", "West", "Nordwest"]);
});

test("detects pointer interaction along each radar axis and near its label", () => {
    const width = 360;
    const height = 340;
    const centerX = width * 0.5;
    const centerY = height * 0.48;
    const labelRadius = Math.min(width, height) / 2 * 0.65 + 20;
    const radarOrder = [0, 7, 6, 5, 4, 3, 2, 1];
    radarOrder.forEach((directionIndex, displayIndex) => {
        const angle = (90 + displayIndex * 45) * Math.PI / 180;
        const x = centerX + labelRadius * Math.cos(angle);
        const y = centerY - labelRadius * Math.sin(angle);
        assert.equal(core.directionIndexAtPoint(x, y, width, height), directionIndex);

        const axisRadius = Math.min(width, height) / 2 * 0.65;
        const axisX = centerX + axisRadius * 0.5 * Math.cos(angle);
        const axisY = centerY - axisRadius * 0.5 * Math.sin(angle);
        assert.equal(core.directionIndexAtPoint(axisX, axisY, width, height), directionIndex);
    });
    assert.equal(core.directionIndexAtPoint(centerX, centerY, width, height), null);
    assert.equal(core.directionIndexAtPoint(20, 20, width, height), null);
});

test("calculates mean speed and maximum gust for matched direction timestamps", () => {
    const result = core.calculate(
        [[1000, 350], [2000, 5], [3000, 45], [4000, 90], [5000, 180]],
        [[1000, 4], [2000, 8], [3000, 3], [4000, 0], [6000, 99]],
        [[1000, 7], [2000, 12], [3000, 9], [4000, 2], [6000, 100]]);
    assert.deepEqual(result.directions, ["N", "NO", "O", "SO", "S", "SW", "W", "NW"]);
    assert.deepEqual(result.speed, [6, 3, 0, 0, 0, 0, 0, 0]);
    assert.deepEqual(result.gust, [12, 9, 2, 0, 0, 0, 0, 0]);
    assert.equal(result.axisMax, 15);
});

test("empty, missing, and invalid readings do not fabricate measurements", () => {
    const result = core.calculate(
        [[0, null], [1000, 45], [2000, 360], [3000, 90]],
        [[1000, 2], [2000, -1], [3000, 5]],
        [[1000, 4], [2000, 8], [3000, null]]);
    assert.deepEqual(result.speed, [0, 2, 0, 0, 0, 0, 0, 0]);
    assert.deepEqual(result.gust, [8, 4, 0, 0, 0, 0, 0, 0]);
    const empty = core.calculate([], [], []);
    assert.deepEqual(empty.speed, [0, 0, 0, 0, 0, 0, 0, 0]);
    assert.deepEqual(empty.gust, [0, 0, 0, 0, 0, 0, 0, 0]);
    assert.equal(empty.axisMax, 5);
});

test("builds an ECharts radar option with wind-speed and gust series", () => {
    const data = core.calculate([[1000, 90]], [[1000, 4]], [[1000, 8]]);
    const option = core.buildOption(data, {
        speedName: "Wind speed",
        gustName: "Gust",
        unit: "km/h",
        speedColor: "#123456",
        gustColor: "#abcdef",
        directionLabels: ["Nord", "Nordost", "Ost", "Südost", "Süd", "Südwest", "West", "Nordwest"],
        format: (value) => String(value),
    });
    assert.equal(option.series[0].type, "radar");
    assert.deepEqual(option.radar.indicator.map((item) => item.name),
        ["Nord", "Nordwest", "West", "Südwest", "Süd", "Südost", "Ost", "Nordost"]);
    assert.equal(option.series[0].data[0].name, "Wind speed");
    assert.equal(option.series[0].data[1].name, "Gust");
    assert.deepEqual(option.color, ["#123456", "#abcdef"]);
    assert.equal(option.series[0].data[0].lineStyle.color, "#123456");
    assert.equal(option.series[0].data[1].lineStyle.color, "#abcdef");
    assert.equal(option.series[0].data[0].value[6], 4);
    assert.equal(option.series[0].data[1].value[6], 8);
    assert.equal(option.tooltip.show, false);
});
