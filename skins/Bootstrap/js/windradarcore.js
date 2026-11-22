(function (root, factory) {
    if (typeof module === "object" && module.exports) {
        module.exports = factory();
    } else {
        root.WindRadarCore = factory();
    }
}(typeof self !== "undefined" ? self : this, function () {
    "use strict";

    const DIRECTIONS = ["N", "NO", "O", "SO", "S", "SW", "W", "NW"];
    const RADAR_ORDER = [0, 7, 6, 5, 4, 3, 2, 1];
    const DEFAULT_COLORS = ["#428bca", "#b44242"];

    function finite(value) {
        return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
    }

    function sectorIndex(direction) {
        let normalized = ((Number(direction) % 360) + 360) % 360;
        return Math.floor((normalized + 22.5) / 45) % DIRECTIONS.length;
    }

    function directionIndexAtPoint(x, y, width, height, hitRadius) {
        let viewSize = Math.min(width, height) / 2;
        let axisRadius = viewSize * 0.65;
        let labelRadius = axisRadius + 20;
        let centerX = width * 0.5;
        let centerY = height * 0.48;
        let labelHitRadius = hitRadius === undefined ? 38 : hitRadius;
        let axisHitRadius = hitRadius === undefined ? 9 : hitRadius;
        let closestIndex = -1;
        let closestDistance = labelHitRadius;

        for (let displayIndex = 0; displayIndex < RADAR_ORDER.length; displayIndex++) {
            let angle = (90 + displayIndex * 45) * Math.PI / 180;
            let labelX = centerX + labelRadius * Math.cos(angle);
            let labelY = centerY - labelRadius * Math.sin(angle);
            let distance = Math.hypot(x - labelX, y - labelY);
            if (distance <= closestDistance) {
                closestDistance = distance;
                closestIndex = RADAR_ORDER[displayIndex];
            }
        }
        if (closestIndex >= 0) {
            return closestIndex;
        }

        let offsetX = x - centerX;
        let offsetY = centerY - y;
        for (let displayIndex = 0; displayIndex < RADAR_ORDER.length; displayIndex++) {
            let angle = (90 + displayIndex * 45) * Math.PI / 180;
            let axisX = Math.cos(angle);
            let axisY = Math.sin(angle);
            let alongAxis = offsetX * axisX + offsetY * axisY;
            let acrossAxis = Math.abs(offsetX * axisY - offsetY * axisX);
            if (alongAxis >= 12 && alongAxis <= axisRadius + axisHitRadius && acrossAxis <= axisHitRadius) {
                return RADAR_ORDER[displayIndex];
            }
        }
        return null;
    }

    function indexedValues(rows) {
        let result = new Map();
        for (let row of rows || []) {
            if (Array.isArray(row) && finite(row[0]) && finite(row[1])) {
                result.set(Number(row[0]), Number(row[1]));
            }
        }
        return result;
    }

    function calculate(directionRows, speedRows, gustRows) {
        let directions = indexedValues(directionRows);
        let speeds = indexedValues(speedRows);
        let gusts = indexedValues(gustRows);
        let speedSums = DIRECTIONS.map(function () { return 0; });
        let speedCounts = DIRECTIONS.map(function () { return 0; });
        let gustMaxima = DIRECTIONS.map(function () { return 0; });

        for (let [timestamp, direction] of directions) {
            let index = sectorIndex(direction);
            let speed = speeds.get(timestamp);
            if (speed !== undefined && speed >= 0) {
                speedSums[index] += speed;
                speedCounts[index]++;
            }
            let gust = gusts.get(timestamp);
            if (gust !== undefined && gust >= 0) {
                gustMaxima[index] = Math.max(gustMaxima[index], gust);
            }
        }

        let speed = speedSums.map(function (sum, index) {
            return speedCounts[index] === 0 ? 0 : sum / speedCounts[index];
        });
        let maximum = Math.max.apply(null, speed.concat(gustMaxima));
        let axisMax = Math.max(5, Math.ceil(maximum / 5) * 5);
        return {
            directions: DIRECTIONS.slice(),
            speed: speed,
            gust: gustMaxima,
            axisMax: axisMax,
        };
    }

    function buildOption(data, config) {
        config = config || {};
        let speedName = config.speedName || "Wind speed";
        let gustName = config.gustName || "Gust";
        let speedColor = config.speedColor || DEFAULT_COLORS[0];
        let gustColor = config.gustColor || DEFAULT_COLORS[1];
        let unit = config.unit || "";
        let decimals = Number.isInteger(config.decimals) ? config.decimals : 1;
        let format = config.format || function (value) { return Number(value).toFixed(decimals); };
        let suffix = unit ? " " + unit : "";
        let directionLabels = Array.isArray(config.directionLabels) &&
            config.directionLabels.length === DIRECTIONS.length ? config.directionLabels : data.directions;
        let radarDirections = RADAR_ORDER.map(function (index) { return directionLabels[index]; });
        let radarSpeed = RADAR_ORDER.map(function (index) { return data.speed[index]; });
        let radarGust = RADAR_ORDER.map(function (index) { return data.gust[index]; });
        return {
            animationDurationUpdate: 400,
            color: [speedColor, gustColor],
            legend: {bottom: 0, data: [speedName, gustName]},
            radar: {
                triggerEvent: true,
                indicator: radarDirections.map(function (name) {
                    return {name: name, max: data.axisMax};
                }),
                center: ["50%", "48%"],
                radius: "65%",
                startAngle: 90,
                splitNumber: 4,
                shape: "polygon",
                axisName: {color: "#555", fontWeight: "bold"},
                splitArea: {areaStyle: {color: ["#fff", "#f7f9fb"]}},
                splitLine: {lineStyle: {color: "#c8d0d8"}},
                axisLine: {lineStyle: {color: "#aab4be"}},
            },
            tooltip: {show: false},
            series: [{
                type: "radar",
                data: [
                    {
                        name: speedName,
                        value: radarSpeed,
                        areaStyle: {opacity: 0.18},
                        lineStyle: {color: speedColor, width: 2},
                        itemStyle: {color: speedColor},
                        symbolSize: 4,
                    },
                    {
                        name: gustName,
                        value: radarGust,
                        areaStyle: {opacity: 0.12},
                        lineStyle: {color: gustColor, width: 2},
                        itemStyle: {color: gustColor},
                        symbolSize: 4,
                    },
                ],
            }],
        };
    }

    return {
        DIRECTIONS: DIRECTIONS,
        sectorIndex: sectorIndex,
        directionIndexAtPoint: directionIndexAtPoint,
        calculate: calculate,
        buildOption: buildOption,
    };
}));
