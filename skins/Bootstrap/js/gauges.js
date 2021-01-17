let gauges = {};
for(let gaugeId of Object.keys(weewxData.gauges)) {
    let documentGaugeId = gaugeId + "Gauge";
    let gauge = echarts.init(document.getElementById(documentGaugeId));
    gauge.weewxData = weewxData.gauges[gaugeId];
    gauges[documentGaugeId] = gauge;
    let colors = [];
    let minvalue = gauge.weewxData.minvalue;
    let maxvalue = gauge.weewxData.maxvalue;
    let splitnumber = gauge.weewxData.splitnumber;
    if(gauge.weewxData.obs_group === "group_direction") {
        minvalue = 0;
        maxvalue = 360;
        splitnumber = 4;
        colors = [[0.25, gauge.weewxData.lineColorN], [0.5, gauge.weewxData.lineColorS], [0.75, gauge.weewxData.lineColorS], [1, gauge.weewxData.lineColorN]];
    } else {
        let lineColors = Array.isArray(gauge.weewxData.lineColor) ? gauge.weewxData.lineColor : [gauge.weewxData.lineColor];
        let lineColorUntilValues = Array.isArray(gauge.weewxData.lineColorUntil) ? gauge.weewxData.lineColorUntil : [gauge.weewxData.lineColorUntil];
        let range = maxvalue - minvalue;
        for(let i = 0; i < lineColors.length; i++) {
            let untilValue = lineColorUntilValues[i].toLowerCase();
            if(isNaN(untilValue)) {
                if(untilValue === 'maxvalue') {
                    untilValue = maxvalue;
                } else if(untilValue === 'minvalue') {
                    untilValue = minvalue;
                } else {
                    console.log("Invalid value: " + untilValue);
                    untilValue = maxvalue;
                }
            }
            colors.push([(untilValue - minvalue)/range, lineColors[i]]);
        }
    }
    let gaugeOption = getGaugeOption(weewxData.labels.Generic[gaugeId], minvalue, maxvalue, splitnumber, colors,  weewxData.units.Labels[gauge.weewxData.target_unit], gauge.weewxData.decimals, weewxData[gaugeId]);
    if(gauge.weewxData.obs_group === "group_direction") {
        gaugeOption.series[0].startAngle = 90;
        gaugeOption.series[0].endAngle = -270;
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

function getGaugeOption(name, min, max, splitNumber, lineColor, unit, decimals, data) {
    decimals = Number(decimals);
    if(data === undefined || data.length < 1) {
      data = 0;
    } else {
      data = data.slice(-1)[0][1];
    }
    return {
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
                        if(decimals !== undefined && decimals >= 0) {
                          return value.toFixed(decimals) + unit;
                        } else {
                          return value + unit;
                        }
                    },
                    offsetCenter: ['0', '70%']
                },
                data: [{
                        value: data,
                        name: name
                    }
                ]
            }
        ]
    };
}
$(window).on('resize', function(){
    for(let gaugeId of Object.keys(gauges)) {
        let gauge = gauges[gaugeId];
        if(gauge != null && gauge != undefined){
            gauge.resize();
        }
    }
});