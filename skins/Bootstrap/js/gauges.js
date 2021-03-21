let maxOpacity = 255 * 0.55;
for (let gaugeId of Object.keys(weewxData.gauges)) {
    let documentGaugeId = gaugeId + "Gauge";
    let gaugeElement = document.getElementById(documentGaugeId);
    if (gaugeElement === null || gaugeElement === undefined) {
        continue;
    }
    let gauge = echarts.init(gaugeElement);
    gauge.weewxData = weewxData.gauges[gaugeId];
    gauge.weewxData.observationType = gaugeId;
    gauge.weewxData.dataset = {
        weewxColumn: gaugeId
    };
    gauge.weewxData.dataset.data = JSON.parse(JSON.stringify(weewxData[gaugeId]));
    gauges[documentGaugeId] = gauge;
    let colors = [];
    let minvalue = gauge.weewxData.minvalue;
    let maxvalue = gauge.weewxData.maxvalue;
    let splitnumber = gauge.weewxData.splitnumber;
    let axisTickSplitNumber = 5;
    if (gauge.weewxData.heatMapEnabled !== undefined && gauge.weewxData.heatMapEnabled.toLowerCase() === "false") {
        gauge.weewxData.heatMapEnabled = false;
    } else {
        gauge.weewxData.heatMapEnabled = true;
    }
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
            }
            colors.push([(untilValue - minvalue) / range, lineColors[i]]);
        }
    }
    let gaugeOption = getGaugeOption(weewxData.labels.Generic[gaugeId], minvalue, maxvalue, splitnumber, axisTickSplitNumber, colors, weewxData.units.Labels[gauge.weewxData.target_unit], gauge.weewxData);
    if (gauge.weewxData.obs_group === "group_direction") {
        gaugeOption.animation = gauge.weewxData.animation !== undefined && gauge.weewxData.animation.toLowerCase() === "true";
        gaugeOption.series[0].startAngle = 90;
        gaugeOption.series[0].endAngle = -270;
        if(gaugeOption.series[1] !== undefined){
            gaugeOption.series[1].startAngle = 90;
            gaugeOption.series[1].endAngle = -270;
        }
        gaugeOption.series[0].axisLabel.distance = 10;
        gaugeOption.series[0].axisLabel.fontSize = 12;
        gaugeOption.series[0].axisLabel.fontWeight = 'bold';
        gaugeOption.series[0].axisLabel.formatter = function (value) {
            if (value === 0)
                return 'N';
            if (value === 90)
                return 'O';
            if (value === 180)
                return 'S';
            if (value === 270)
                return 'W';
        };
        gaugeOption.series[0].title.offsetCenter = ['0', '-25%'];
        gaugeOption.series[0].detail.offsetCenter = ['0', '30%'];
    }
    gauge.setOption(gaugeOption);
}

function getGaugeOption(name, min, max, splitNumber, axisTickSplitNumber, lineColor, unit, weewxData) {
    let decimals = Number(weewxData.decimals);
    let value;
    let data = weewxData.dataset.data;
    if (data === undefined || data.length < 1) {
        value = 0;
    } else {
        value = data.slice(-1)[0][1];
    }
    let option = {
        animation: weewxData.animation === undefined || !weewxData.animation.toLowerCase() === "false",
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
                    fontSize: 8,
                    color: '#777'
                },
                title: {
                    fontWeight: 'normal',
                    fontSize: 10,
                    color: '#777',
                    offsetCenter: ['0', '28%']
                },
                detail: {
                    fontWeight: 'bold',
                    fontSize: 12,
                    color: '#777',
                    formatter: function (value) {
                        if (decimals !== undefined && decimals >= 0) {
                            return value.toFixed(decimals) + unit;
                        } else {
                            return value + unit;
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
    let ticksNumber = splitNumber * axisTickSplitNumber;
    let range = max - min;
    let ticksRange = (range / ticksNumber);
    let splitValueCount = Array.apply(null, Array(ticksNumber)).map(function () {
            return 0;
        });
    let baseColor = '#ff0000';
    for (let item of data) {
        let value = item[1];
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
