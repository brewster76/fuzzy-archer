let outTempChart = echarts.init(document.getElementById('outTempChart'));
let outTempChartSeriesConfigs =
    [{
        name: 'Temperatur',
        decimals: 1,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: true
    }, {
        name: 'Taupunkt',
        decimals: 1,
        showMaxMarkPoint: false,
        showMinMarkPoint: false,
        showAvgMarkLine: false
    }
];
outTempChart.setOption(getLineChartOption('°C', outTempChartSeriesConfigs));

let barometerChart = echarts.init(document.getElementById('barometerChart'));
let barometerChartSeriesConfigs =
    [{
        name: 'Luftdruck',
        decimals: 1,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: false
    }
];
barometerChart.setOption(getLineChartOption('mbar', barometerChartSeriesConfigs));

let rainChart = echarts.init(document.getElementById('rainChart'));
let rainChartOption = {
    legend: {
        type: "plain"
    },
    textStyle: {
        fontSize: 10,
    },
    color: ['#428bca'],
    backgroundColor: '#1111110a',
    toolbox: {
        show: true,
        feature: {
            dataZoom: {
                yAxisIndex: "none"
            }
        }
    },
    tooltip: {
        trigger: "axis",
        axisPointer: {
            type: "line"
        },
        show: true,

        position: function (pt) {
            return [pt[0], 200];
        },
    },
    label: {
        align: 'left'
    },
    xAxis: {
        show: true,
        minInterval: 30 * 60000, // 30 minutes
        axisLine: {
            show: false
        },
        axisTick: {
            show: false
        },
        type: "time",
        splitLine: {
            show: true
        }
    },
    yAxis: {
        name: "mm",
        type: "value",
        min: 0,
        minInterval: 1,
        nameTextStyle: {
            fontWeight: 'bold',
        },
        axisLabel: {
            formatter: "{value}"
        }
    },
    series: [{
            name: "Niederschlag",
            type: "bar",
            data: [],
            barWidth: '100%'
        }
    ]
}
rainChart.setOption(rainChartOption);

let outHumidityChart = echarts.init(document.getElementById('outHumidityChart'));
let outHumidityChartSeriesConfigs =
    [{
        name: 'Luftfeuchte',
        decimals: 0,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: false
    }
];
let outHumidityChartOption = getLineChartOption('%', outHumidityChartSeriesConfigs);
outHumidityChartOption.yAxis.min = 0;
outHumidityChartOption.yAxis.max = 100;
outHumidityChart.setOption(outHumidityChartOption);

let windChart = echarts.init(document.getElementById('windChart'));
let windChartSeriesConfigs =
    [{
        name: 'Wind',
        decimals: 0,
        showMaxMarkPoint: false,
        showMinMarkPoint: false,
        showAvgMarkLine: false
    }, {
        name: 'Böen',
        decimals: 0,
        showMaxMarkPoint: true,
        showMinMarkPoint: false,
        showAvgMarkLine: false
    }
];
let windChartOption = getLineChartOption('km/h', windChartSeriesConfigs);
windChartOption.yAxis.min = 0;
windChart.setOption(windChartOption);

let windDirChart = echarts.init(document.getElementById('windDirChart'));
let windDirChartSeriesConfigs =
    [{
        name: 'Windrichtung',
        showMaxMarkPoint: false,
        showMinMarkPoint: false,
        showAvgMarkLine: false,
        symbol: 'circle',
        symbolSize: 1,
        lineStyle: {
            width: 0,
        },
    }
];
let windDirChartOption = getLineChartOption('°', windDirChartSeriesConfigs);
windDirChartOption.yAxis.min = 0;
windDirChartOption.yAxis.max = 360;
windDirChartOption.yAxis.minInterval = 90;
windDirChartOption.yAxis.maxInterval = 90;
windDirChart.setOption(windDirChartOption);

let pvOutputChart = echarts.init(document.getElementById('pvOutputChart'));
let pvOutputChartSeriesConfigs =
    [{
        name: 'PV Output',
        decimals: 0,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: false
    }
];
let pvOutputOption = getLineChartOption('kw/kwP', pvOutputChartSeriesConfigs);
pvOutputOption.yAxis.min = 0;
pvOutputOption.yAxis.minInterval = 0.05;
pvOutputChart.setOption(pvOutputOption);

function getLineChartOption(yAxisName, seriesConfigs) {
    let series = [];
    for (let seriesConfig of seriesConfigs) {
        let serie = {
            name: seriesConfig.name,
            type: "line",
            symbol: seriesConfig.symbol === undefined ? 'none' : seriesConfig.symbol,
            lineStyle: {
                width: seriesConfig.lineStyle === undefined || seriesConfig.lineStyle.width === undefined ? 1 : seriesConfig.lineStyle.width,
            },
            data: [],
        };

        if (seriesConfig.showMaxMarkPoint || seriesConfig.showMinMarkPoint) {
            let markPoint = {};
            markPoint.symbolSize = 0;
            markPoint.data = [];
            if (seriesConfig.showMaxMarkPoint) {
                markPoint.data.push({
                    type: "max",
                    name: "Max",
                    label: {
                        show: true,
                        position: "top",
                        formatter: function (value) {
                            return value.data.value.toFixed(seriesConfig.decimals);
                        },
                    }
                });
            }
            if (seriesConfig.showMinMarkPoint) {
                markPoint.data.push({
                    type: "min",
                    name: "Min",
                    label: {
                        show: true,
                        position: "bottom",
                        formatter: function (value) {
                            return value.data.value.toFixed(seriesConfig.decimals);
                        },
                    }
                });
            }
            serie.markPoint = markPoint;
        }
        if (seriesConfig.showAvgMarkLine) {
            serie.markLine = {
                precision: seriesConfig.decimals,
                data: [{
                        type: "average",
                        name: "Avg",
                        label: {
                            formatter: "{c}" + yAxisName
                        }
                    }
                ]
            };
        }

        series.push(serie);
    }

    return {
        legend: {
            type: "plain"
        },
        textStyle: {
            fontSize: 10,
        },
        color: ['#428bca', '#b44242', '#c23531'],
        backgroundColor: '#1111110a',
        toolbox: {
            show: true,
            feature: {
                dataZoom: {
                    yAxisIndex: "none"
                }
            }
        },
        tooltip: {
            trigger: "axis",
            axisPointer: {
                type: "line"
            },
            show: true,

            position: function (pt) {
                return [pt[0], 200];
            },
        },
        xAxis: {
            show: true,
            minInterval: 30 * 60000, // 30 minutes
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            type: "time",
            splitLine: {
                show: true
            }
        },
        yAxis: {
            name: yAxisName,
            type: "value",
            scale: true,
            minInterval: 1,
            nameTextStyle: {
                fontWeight: 'bold',
            },
            axisLabel: {
                formatter: "{value}"
            }
        },
        series: series
    }
}
