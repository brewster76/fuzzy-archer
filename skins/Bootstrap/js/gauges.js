let maxOpacity = 255 * 0.55;
function loadGauges() {
    let gaugePanel = document.getElementById("gaugePanel");
    if(gaugePanel !== null && gaugePanel !== undefined && window.getComputedStyle(gaugePanel).display === 'none') {
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
        gauge.weewxData.dataset.data = aggregate(JSON.parse(JSON.stringify(weewxData[gaugeId])), gauge.weewxData.aggregateInterval, gauge.weewxData.aggregateType);
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
        }
        gauge.setOption(gaugeOption);
    }
}

function parseBooleanDefaultTrue(value) {
    return parseBoolean(value, true);
}

function parseBooleanDefaultFalse(value) {
    return parseBoolean(value, false);
}

function parseBoolean(value, defaultValue) {
    if (value !== undefined && value.toLowerCase() === "false") {
        return false;
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
                color: '#777',
                formatter: function (value, index) {
                    return round(value, 1);
                }
            },
            title: {
                fontWeight: 'normal',
                fontSize: weewxData.titleFontSize === undefined ? 10 : weewxData.titleFontSize,
                color: '#777',
                offsetCenter: ['0', '28%']
            },
            detail: {
                fontWeight: 'bold',
                fontSize: weewxData.detailFontSize === undefined ? 12 : weewxData.detailFontSize,
                color: '#777',
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
});

function getHeatColor(max, min, splitNumber, axisTickSplitNumber, data) {
    if(data === undefined || data === null ){
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
        if(value === null || value === undefined) {
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

function getDecimalSeparator(locale) {
    let n = 1.1;
    n = n.toLocaleString(locale).substring(1, 2);
    return n;
}

var noReadingString = "--";
function format(number, digits) {
    if (number === noReadingString) {
        return number;
    }
    number = Number(number);
    let localeInfo = locale.replace("_", "-");
    let numString = parseFloat(number.toFixed(digits)).toLocaleString(localeInfo);
    let decimalSeparator = getDecimalSeparator(localeInfo);
    if (digits > 0 && !numString.includes(decimalSeparator)) {
        numString += decimalSeparator;
        for (let i = 0; i < digits; i++) {
            numString += "0";
        }
    }
    return numString;
}
