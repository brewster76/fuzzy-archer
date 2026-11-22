let maxOpacity = 255 * 0.55;
let windRadarChart;
let windRadarPinnedDirection = null;
let windRadarTooltip;
let windRadarData;
let windRadarScaleLabels = [];

function loadGauges() {
    let gaugePanel = document.getElementById("gaugePanel");
    if (gaugePanel !== null && gaugePanel !== undefined && window.getComputedStyle(gaugePanel).display === 'none') {
        gaugePanel.remove();
        document.getElementById("mainPanel").setAttribute("class", "col-12 mt-1");
        return;
    }
    for (let gaugeId of Object.keys(weewxData.gauges)) {
        let documentGaugeId = gaugeId + "Gauge";

        if (gauges[documentGaugeId] !== undefined) {
            gauges[documentGaugeId].dispose();
            gauges[documentGaugeId] = undefined;
        }

        let gaugeElement = document.getElementById(documentGaugeId);
        if (gaugeElement === null || gaugeElement === undefined) {
            continue;
        }
        let gauge = echarts.init(gaugeElement, null, {
            locale: eChartsLocale
        });
        gauge.weewxData = weewxData.gauges[gaugeId];
        gauge.weewxData.observationType = gaugeId;
        gauge.weewxData.dataset = {
            weewxColumn: gaugeId
        };
        gauge.weewxData.dataset.data = aggregate(JSON.parse(JSON.stringify(weewxData[gaugeId])), gauge.weewxData.aggregateInterval, gauge.weewxData.aggregateType, gauge.weewxData.decimals);
        gauges[documentGaugeId] = gauge;
        let colors = [];
        let gaugePitchPrecision = gauge.weewxData["gauge_pitch_precision"] === undefined ? 1 : gauge.weewxData["gauge_pitch_precision"];
        let minvalue = gauge.weewxData.minvalue;
        let maxvalue = gauge.weewxData.maxvalue;
        let splitnumber = gauge.weewxData.splitnumber;
        let gaugeName = gauge.weewxData.gaugeName === undefined ? weewxData.labels.Generic[gaugeId] : gauge.weewxData.gaugeName;
        let axisTickSplitNumber = 5;
        gauge.weewxData.heatMapEnabled = parseBooleanDefaultTrue(gauge.weewxData.heatMapEnabled);
        gauge.weewxData.stuckNeedleEnabled = parseBooleanDefaultTrue(gauge.weewxData.stuckNeedleEnabled);
        if (gauge.weewxData.obs_group === "group_direction") {
            minvalue = 0;
            maxvalue = 360;
            splitnumber = 4;
            axisTickSplitNumber = 4;
            colors = [[0.25, gauge.weewxData.lineColorN], [0.5, gauge.weewxData.lineColorS], [0.75, gauge.weewxData.lineColorS], [1, gauge.weewxData.lineColorN]];
            gauge.weewxData.directionValuesEnabled = parseBooleanDefaultFalse(gauge.weewxData.directionValuesEnabled);
        } else {
            let lineColors = Array.isArray(gauge.weewxData.lineColor) ? gauge.weewxData.lineColor : [gauge.weewxData.lineColor];
            let lineColorUntilValues = Array.isArray(gauge.weewxData.lineColorUntil) ? gauge.weewxData.lineColorUntil : [gauge.weewxData.lineColorUntil];
            let range = maxvalue - minvalue;
            for (let i = 0; i < lineColors.length; i++) {
                let untilValue = lineColorUntilValues[i].toLowerCase();
                if (isNaN(untilValue)) {
                    if (untilValue === 'maxvalue') {
                        untilValue = maxvalue;
                    } else if (untilValue === 'minvalue') {
                        untilValue = minvalue;
                    } else {
                        console.log("Invalid value: " + untilValue);
                        untilValue = maxvalue;
                    }
                } else {
                    untilValue = untilValue;
                }
                colors.push([(untilValue - minvalue) / range, lineColors[i]]);
            }
        }
        let gaugeOption = getGaugeOption(gaugeName, minvalue, maxvalue, splitnumber, axisTickSplitNumber, colors, weewxData.units.Labels[gauge.weewxData.target_unit], gauge.weewxData);
        if (gauge.weewxData.obs_group === "group_direction") {
            gauge.isCircular = true;
            gaugeOption.series[0].startAngle = 90;
            gaugeOption.series[0].endAngle = -270;
            if (gaugeOption.series[1] !== undefined) {
                gaugeOption.series[1].startAngle = 90;
                gaugeOption.series[1].endAngle = -270;
            }
            gaugeOption.series[0].axisLabel.distance = 10;
            gaugeOption.series[0].axisLabel.fontSize = gauge.weewxData.labelFontSize === undefined ? 12 : gauge.weewxData.labelFontSize;
            gaugeOption.series[0].axisLabel.fontWeight = 'bold';
            gaugeOption.series[0].axisLabel.formatter = function (value) {
                if (value === 0)
                    return weewxData.labels.hemispheres === undefined ? "N" : weewxData.labels.hemispheres[0];
                if (value === 90)
                    return weewxData.labels.hemispheres === undefined ? "E" : weewxData.labels.hemispheres[2];
                if (value === 180)
                    return weewxData.labels.hemispheres === undefined ? "S" : weewxData.labels.hemispheres[1];
                if (value === 270)
                    return weewxData.labels.hemispheres === undefined ? "W" : weewxData.labels.hemispheres[3];
            };
            gaugeOption.series[0].title.offsetCenter = ['0', '-25%'];
            gaugeOption.series[0].detail.offsetCenter = ['0', '30%'];
            if (gauge.weewxData.directionValuesEnabled) {
                gaugeOption.series[0].detail.formatter = function (value) {
                    let ordinals = weewxData.units.Ordinates.directions === undefined ? ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW', 'N/A'] : weewxData.units.Ordinates.directions;
                    if (isNaN(value)) {
                        return ordinals[-1];
                    }
                    let sectorSize = 360.0 / ((ordinals.length) - 1);
                    let degree = (value + sectorSize / 2.0) % 360.0;
                    let sector = Math.floor(degree / sectorSize);
                    return ordinals[sector];
                };
            }
        }
        gauge.setOption(gaugeOption);
    }
    loadWindRadar();
}

function isWindRadarEnabled() {
    let enabled = weewxData && weewxData.gauges && weewxData.gauges.wind_radar &&
        weewxData.gauges.wind_radar.enabled;
    return enabled !== undefined && enabled !== null && String(enabled).toLowerCase() === "true";
}

function loadWindRadar() {
    let element = document.getElementById("windRadarChart");
    if (!isWindRadarEnabled() || element === null || element === undefined) {
        if (windRadarChart !== undefined) {
            windRadarChart.dispose();
            windRadarChart = undefined;
        }
        if (windRadarTooltip !== undefined) {
            windRadarTooltip.remove();
            windRadarTooltip = undefined;
        }
        windRadarPinnedDirection = null;
        return;
    }

    if (windRadarChart === undefined) {
        windRadarChart = echarts.init(element, null, {locale: eChartsLocale});
        windRadarTooltip = document.createElement("div");
        windRadarTooltip.className = "windRadarTooltip";
        windRadarTooltip.setAttribute("role", "tooltip");
        windRadarTooltip.setAttribute("aria-live", "polite");
        element.appendChild(windRadarTooltip);
        windRadarScaleLabels = [];
        for (let i = 0; i < 4; i++) {
            let label = document.createElement("div");
            label.className = "windRadarScaleLabel";
            label.setAttribute("aria-hidden", "true");
            element.appendChild(label);
            windRadarScaleLabels.push(label);
        }

        windRadarChart.getZr().on("mousemove", function (event) {
            if (windRadarPinnedDirection !== null) {
                return;
            }
            let direction = getWindRadarDirectionAtEvent(event);
            element.style.cursor = direction === null ? "" : "pointer";
            showWindRadarTooltip(direction, event);
        });
        windRadarChart.getZr().on("click", function (event) {
            let direction = getWindRadarDirectionAtEvent(event);
            windRadarPinnedDirection = direction;
            element.style.cursor = direction === null ? "" : "pointer";
            showWindRadarTooltip(direction, event);
        });
        windRadarChart.getZr().on("globalout", function () {
            if (windRadarPinnedDirection === null) {
                element.style.cursor = "";
                showWindRadarTooltip(null);
            }
        });
    }
    updateWindRadar();
}

function getWindRadarDirectionAtEvent(event) {
    let x = Number(event.offsetX);
    let y = Number(event.offsetY);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
        return null;
    }
    return WindRadarCore.directionIndexAtPoint(
        x, y, windRadarChart.getWidth(), windRadarChart.getHeight());
}

function showWindRadarTooltip(directionIndex, event) {
    if (windRadarTooltip === undefined) {
        return;
    }
    if (directionIndex === null || directionIndex === undefined) {
        windRadarTooltip.style.display = "none";
        return;
    }
    let labels = getWindRadarDirectionLabels();
    let speedConfig = weewxData.gauges.windSpeed || {};
    let gustConfig = weewxData.gauges.windGust || {};
    let decimals = Number.isInteger(Number(speedConfig.decimals)) ? Number(speedConfig.decimals) : 1;
    let unit = weewxData.units.Labels[speedConfig.target_unit] || "";
    if (windRadarData === undefined) {
        updateWindRadar();
    }
    let heading = document.createElement("div");
    heading.className = "windRadarTooltipHeading";
    heading.textContent = labels[directionIndex];
    let rows = [
        [speedConfig.gaugeName || weewxData.labels.Generic.windSpeed || "Wind speed", windRadarData.speed[directionIndex]],
        [gustConfig.gaugeName || weewxData.labels.Generic.windGust || "Gust", windRadarData.gust[directionIndex]],
    ];
    while (windRadarTooltip.firstChild !== null) {
        windRadarTooltip.removeChild(windRadarTooltip.firstChild);
    }
    windRadarTooltip.appendChild(heading);
    for (let row of rows) {
        let line = document.createElement("div");
        line.textContent = decodeHtml(row[0]) + ": " + format(row[1], decimals) + getUnitString(row[1], unit);
        windRadarTooltip.appendChild(line);
    }
    let x = Number(event && event.offsetX);
    let y = Number(event && event.offsetY);
    let width = windRadarChart.getWidth();
    let height = windRadarChart.getHeight();
    windRadarTooltip.style.display = "block";
    windRadarTooltip.style.left = Math.max(0, Math.min(Number.isFinite(x) ? x + 12 : width / 2, width - windRadarTooltip.offsetWidth)) + "px";
    windRadarTooltip.style.top = Math.max(0, Math.min(Number.isFinite(y) ? y + 12 : height / 2, height - windRadarTooltip.offsetHeight)) + "px";
}

function getWindRadarDirectionLabels() {
    let configured = weewxData.units && weewxData.units.Ordinates && weewxData.units.Ordinates.directions;
    if (Array.isArray(configured) && configured.length >= 16) {
        return configured.filter(function (_, index) { return index % 2 === 0; }).slice(0, 8);
    }
    if (Array.isArray(configured) && configured.length === 8) {
        return configured.slice();
    }
    return WindRadarCore.DIRECTIONS.slice();
}

function getWindRadarRows(observation) {
    let cutoff = Date.now() - maxAgeHoursMS;
    let valuesByTimestamp = new Map();
    let history = weewxData[observation];
    if (Array.isArray(history)) {
        for (let row of history) {
            if (Array.isArray(row) && row[1] !== null && row[1] !== undefined && row[1] !== "" &&
                Number.isFinite(Number(row[0])) && Number(row[0]) >= cutoff && Number.isFinite(Number(row[1]))) {
                valuesByTimestamp.set(Number(row[0]), Number(row[1]));
            }
        }
    }

    let gaugeConfig = weewxData.gauges[observation];
    if (gaugeConfig !== undefined && gaugeConfig.payload_key !== undefined) {
        for (let entry of liveData) {
            let timestamp = Number(entry[0]);
            if (timestamp < cutoff) {
                continue;
            }
            let raw = getValue(entry[1], gaugeConfig.payload_key);
            if (raw === null || raw === undefined || raw === "") {
                continue;
            }
            let value = convert(Object.assign({observationType: observation}, gaugeConfig), raw);
            if (Number.isFinite(Number(value))) {
                valuesByTimestamp.set(timestamp, Number(value));
            }
        }
    }
    return Array.from(valuesByTimestamp.entries()).sort(function (left, right) {
        return left[0] - right[0];
    });
}

function updateWindRadar() {
    if (windRadarChart === undefined || !isWindRadarEnabled()) {
        return;
    }
    windRadarData = WindRadarCore.calculate(
        getWindRadarRows("windDir"),
        getWindRadarRows("windSpeed"),
        getWindRadarRows("windGust"));
    let speedConfig = weewxData.gauges.windSpeed || {};
    let gustConfig = weewxData.gauges.windGust || {};
    let unit = weewxData.units.Labels[speedConfig.target_unit] || "";
    let decimals = Number.isInteger(Number(speedConfig.decimals)) ? Number(speedConfig.decimals) : 1;
    let speedName = speedConfig.gaugeName === undefined ?
        (weewxData.labels.Generic.windSpeed || "Wind speed") : decodeHtml(speedConfig.gaugeName);
    let gustName = gustConfig.gaugeName === undefined ?
        (weewxData.labels.Generic.windGust || "Gust") : decodeHtml(gustConfig.gaugeName);
    let radarConfig = weewxData.gauges.wind_radar || {};
    let speedColor = radarConfig.wind_speed_color;
    let gustColor = radarConfig.wind_gust_color;
    windRadarChart.setOption(WindRadarCore.buildOption(windRadarData, {
        speedName: speedName,
        gustName: gustName,
        speedColor: speedColor,
        gustColor: gustColor,
        directionLabels: getWindRadarDirectionLabels(),
        unit: unit,
        decimals: decimals,
        format: function (value) { return format(value, decimals); },
    }));
    updateWindRadarScaleLabels(decimals);
}

function updateWindRadarScaleLabels(decimals) {
    let width = windRadarChart.getWidth();
    let height = windRadarChart.getHeight();
    let centerX = width * 0.5;
    let centerY = height * 0.48;
    let radius = Math.min(width, height) / 2 * 0.65;
    let step = windRadarData.axisMax / windRadarScaleLabels.length;
    for (let index = 0; index < windRadarScaleLabels.length; index++) {
        let value = step * (index + 1);
        let label = windRadarScaleLabels[index];
        label.textContent = format(value, decimals);
        label.style.left = (centerX + 5) + "px";
        label.style.top = (centerY - radius * (index + 1) / windRadarScaleLabels.length) + "px";
    }
}

function parseBooleanDefaultTrue(value) {
    return parseBoolean(value, true);
}

function parseBooleanDefaultFalse(value) {
    return parseBoolean(value, false);
}

function parseBoolean(value, defaultValue) {
    if (value !== undefined && value !== null) {
        if (value.toLowerCase() === "false") {
            return false;
        } else if (value.toLowerCase() === "true") {
            return true;
        }
    }
    return defaultValue;
}

function getGaugeOption(name, min, max, splitNumber, axisTickSplitNumber, lineColor, unit, weewxData) {
    name = decodeHtml(name);
    let decimals = Number(weewxData.decimals);
    let value = null;
    let data = weewxData.dataset.data;
    if (data === undefined || data.length < 1) {
        value = null;
    } else {
        let index = 1;
        while (value === null && index <= data.length) {
            value = data.slice(index++ * -1)[0][1];
            if (!weewxData.stuckNeedleEnabled) {
                break;
            }
        }
    }
    let option = {
        animation: weewxData.animation === undefined || !weewxData.animation.toLowerCase() === "false",
        animationDurationUpdate: 750,
        series: [{
            name: name,
            type: 'gauge',
            min: Number(min),
            max: Number(max),
            splitNumber: Number(splitNumber),
            radius: '95%',
            axisLine: {
                lineStyle: {
                    width: 8,
                    color: lineColor,
                    shadowBlur: 3
                }
            },
            pointer: {
                show: !isNaN(parseFloat(value)),
                width: 5,
                itemStyle: {
                    color: '#428bca',
                    shadowBlur: 3
                }
            },
            axisTick: {
                splitNumber: axisTickSplitNumber,
                length: 4,
                lineStyle: {
                    color: 'auto'
                }
            },
            splitLine: {
                length: 6,
                lineStyle: {
                    color: 'auto'
                }
            },
            axisLabel: {
                fontWeight: 'normal',
                fontSize: weewxData.labelFontSize === undefined ? 8 : weewxData.labelFontSize,
                color: weewxData.labelColor === undefined ? '#777' : weewxData.labelColor,
                formatter: function (value, index) {
                    return round(value, 1);
                }
            },
            title: {
                fontWeight: 'normal',
                fontSize: weewxData.titleFontSize === undefined ? 10 : weewxData.titleFontSize,
                color: weewxData.titleColor === undefined ? '#777' : weewxData.titleColor,
                offsetCenter: ['0', '28%']
            },
            detail: {
                fontWeight: 'bold',
                fontSize: weewxData.detailFontSize === undefined ? 12 : weewxData.detailFontSize,
                color: weewxData.detailColor === undefined ? '#777' : weewxData.detailColor,
                formatter: function (value) {
                    if (isNaN(value)) {
                        return undefined;
                    } else {
                        if (decimals !== undefined && decimals >= 0) {
                            value = format(value, decimals);
                        }
                        return value + getUnitString(value, unit);
                    }
                },
                offsetCenter: ['0', '70%']
            },
            data: [{
                value: value,
                name: name
            }
            ]
        },
        ]
    };
    if (weewxData.heatMapEnabled) {
        option.series.push({
            name: "heat",
            z: -1,
            type: 'gauge',
            min: Number(min),
            max: Number(max),
            splitNumber: 0,
            radius: '95%',
            axisLine: {
                lineStyle: {
                    width: '100%',
                    color: getHeatColor(max, min, splitNumber, axisTickSplitNumber, data),
                    shadowBlur: 3,
                }
            },
            pointer: {
                width: 5,
                itemStyle: {
                    color: '#428bca',
                    shadowBlur: 3
                }
            },
            axisTick: {
                show: false,
            },
            splitLine: {
                show: false,
            },
            axisLabel: {
                show: false,
            }
        });
    }
    return option;
}
$(window).on('resize', function () {
    for (let gaugeId of Object.keys(gauges)) {
        let gauge = gauges[gaugeId];
        if (gauge != null && gauge != undefined) {
            gauge.resize();
        }
    }
    if (windRadarChart !== undefined) {
        windRadarChart.resize();
        updateWindRadar();
    }
});

function getHeatColor(max, min, splitNumber, axisTickSplitNumber, data) {
    if (data === undefined || data === null) {
        return "#ffffff00";
    }
    let ticksNumber = splitNumber * axisTickSplitNumber;
    let range = max - min;
    let ticksRange = (range / ticksNumber);
    let splitValueCount = Array.apply(null, Array(ticksNumber)).map(function () {
        return 0;
    });
    let baseColor = '#ff0000';
    for (let item of data) {
        let value = item[1];
        if (value === null || value === undefined) {
            continue;
        }
        let index = 0;
        if (value > max) {
            index = splitValueCount.length - 1;
        } else if (value >= min) {
            index = Math.floor((value - min) / ticksRange);
        }
        splitValueCount[index]++;
    }
    let color = [];
    let ticksWidth = ticksRange / range;
    let until = ticksWidth;
    for (let count of splitValueCount) {
        let weight = Math.floor(maxOpacity * count / data.length);
        let opacity = Number(weight).toString(16);
        if (weight < 16) {
            opacity = "0" + opacity;
        }
        color.push([until, baseColor + opacity]);
        until += ticksWidth;
    }
    return color;
}

function getDecimalSeparator() {
    let n = 1.1;
    n = n.toLocaleString(jsLocale).substring(1, 2);
    return n;
}

var noReadingString = "--";
function format(number, digits) {
    if (number === noReadingString) {
        return number;
    }
    number = Number(number);
    let numString = parseFloat(number.toFixed(digits)).toLocaleString(jsLocale);
    let decimalSeparator = getDecimalSeparator();
    if (digits > 0 && !numString.includes(decimalSeparator)) {
        numString += decimalSeparator;
        for (let i = 0; i < digits; i++) {
            numString += "0";
        }
    }
    return numString;
}
