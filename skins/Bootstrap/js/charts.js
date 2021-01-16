let charts = {};
let outTempChart = echarts.init(document.getElementById('outTempChart'));
charts['outTempChart'] = outTempChart;
let outTempChartSeriesConfigs =
    [{
        name: 'Temperatur',
        decimals: 1,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: true,
        data: weewxData["outTemp"],
        unit: "°C"
    }, {
        name: 'Taupunkt',
        decimals: 1,
        showMaxMarkPoint: false,
        showMinMarkPoint: false,
        showAvgMarkLine: false,
        data: calculateDewpoints(weewxData["outTemp"], weewxData["outHumidity"]),
        unit: "°C"
    }
];
outTempChart.setOption(getLineChartOption('°C', outTempChartSeriesConfigs));

let barometerChart = echarts.init(document.getElementById('barometerChart'));
charts['barometerChart'] = barometerChart;
let barometerChartSeriesConfigs =
    [{
        name: 'Luftdruck',
        decimals: 1,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: false,
        data: weewxData["barometer"],
        unit: "mbar"
    }
];
barometerChart.setOption(getLineChartOption('mbar', barometerChartSeriesConfigs));

let rainChart = echarts.init(document.getElementById('rainChart'));
charts['rainChart'] = rainChart;
let rainChartSeriesConfigs =
    [{
        name: 'Niederschlag',
        decimals: 0,
        showMaxMarkPoint: false,
        showMinMarkPoint: false,
        showAvgMarkLine: false,
        data: weewxData["rain_mm"],
        unit: "mm"
    }
];
let rainChartOption = getBarChartOption("mm", rainChartSeriesConfigs, rainAggregateIntervalMinutes);
rainChart.setOption(rainChartOption);

let outHumidityChart = echarts.init(document.getElementById('outHumidityChart'));
charts['outHumidityChart'] = outHumidityChart;
let outHumidityChartSeriesConfigs =
    [{
        name: 'Luftfeuchte',
        decimals: 0,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: false,
        data: weewxData["outHumidity"],
        unit: "%"
    }
];
let outHumidityChartOption = getLineChartOption('%', outHumidityChartSeriesConfigs);
outHumidityChartOption.yAxis.min = 0;
outHumidityChartOption.yAxis.max = 100;
outHumidityChart.setOption(outHumidityChartOption);

let windChart = echarts.init(document.getElementById('windChart'));
charts['windChart'] = windChart;
let windChartSeriesConfigs =
    [{
        name: 'Wind',
        decimals: 0,
        showMaxMarkPoint: false,
        showMinMarkPoint: false,
        showAvgMarkLine: false,
        data: weewxData["windSpeed"],
        unit: "km/h"
    }, {
        name: 'Böen',
        decimals: 0,
        showMaxMarkPoint: true,
        showMinMarkPoint: false,
        showAvgMarkLine: false,
        data: weewxData["windGust"],
        unit: "km/h"
    }
];
let windChartOption = getLineChartOption('km/h', windChartSeriesConfigs);
windChartOption.yAxis.min = 0;
windChart.setOption(windChartOption);

let windDirChart = echarts.init(document.getElementById('windDirChart'));
charts['windDirChart'] = windDirChart;
let windDirChartSeriesConfigs =
    [{
        name: 'Windrichtung',
        decimals: 1,
        showMaxMarkPoint: false,
        showMinMarkPoint: false,
        showAvgMarkLine: false,
        symbol: 'circle',
        symbolSize: 1,
        lineStyle: {
            width: 0,
        },
        data: weewxData["windDir"],
        unit: "°"
    }
];
let windDirChartOption = getLineChartOption('°', windDirChartSeriesConfigs);
windDirChartOption.yAxis.min = 0;
windDirChartOption.yAxis.max = 360;
windDirChartOption.yAxis.minInterval = 90;
windDirChartOption.yAxis.maxInterval = 90;
windDirChart.setOption(windDirChartOption);

let pvOutputChart = echarts.init(document.getElementById('pvOutputChart'));
charts['pvOutputChart'] = pvOutputChart;
let pvOutputChartSeriesConfigs =
    [{
        name: 'PV Output',
        decimals: 3,
        showMaxMarkPoint: true,
        showMinMarkPoint: true,
        showAvgMarkLine: false,
        unit: "kW/kWp"
    }
];
let pvOutputOption = getLineChartOption('kw/kwP', pvOutputChartSeriesConfigs);
pvOutputOption.yAxis.min = 0;
pvOutputOption.yAxis.minInterval = 0.05;
pvOutputChart.setOption(pvOutputOption);

function getLineChartOption(yAxisName, seriesConfigs) {
    let series = [];
    for (let seriesConfig of seriesConfigs) {
        if (seriesConfig.data === undefined) {
            seriesConfig.data = [];
        }
        let serie = {
            name: seriesConfig.name,
            type: "line",
            symbol: seriesConfig.symbol === undefined ? 'none' : seriesConfig.symbol,
            lineStyle: {
                width: seriesConfig.lineStyle === undefined || seriesConfig.lineStyle.width === undefined ? 1 : seriesConfig.lineStyle.width,
            },
            data: seriesConfig.data,
            decimals: seriesConfig.decimals,
            unitLabel: seriesConfig.unit
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
                        formatter: function (value, ticket) {
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
            formatter: function (params, ticket, callback) {
                let elements = document.querySelectorAll(":hover");
                let option = charts[elements.item(elements.length - 1).parentElement.parentElement.id].getOption();
                let tooltipHTML = '<table><tr><td colspan="2" style="font-size: x-small;">' + moment(params[0].axisValue).format("D.M.YYYY, H:mm:ss") + '</td></tr>';
                params.forEach(item => {
                    let decimals = option.series[item.seriesIndex].decimals;
                    let unitLabel = option.series[item.seriesIndex].unitLabel;
                    tooltipHTML += ('<tr style="font-size: small;"><td>' + item.marker + item.seriesName + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + format(item.data[1], decimals) + unitLabel + '</td></tr>');
                });
                return tooltipHTML + '</table>';
            }
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

function getBarChartOption(yAxisName, seriesConfigs, aggregateIntervalMinutes) {
    let series = [];
    for (let seriesConfig of seriesConfigs) {
        if (seriesConfig.data === undefined) {
            seriesConfig.data = [];
        }
        let serie = {
            name: seriesConfig.name,
            type: "bar",
            barWidth: '100%',
            data: seriesConfig.data,
            decimals: seriesConfig.decimals,
            unitLabel: seriesConfig.unit
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
                        formatter: function (value, ticket) {
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
        aggregateIntervalMinutes, aggregateIntervalMinutes,
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
            formatter: function (params, ticket, callback) {
                let elements = document.querySelectorAll(":hover");
                let option = charts[elements.item(elements.length - 1).parentElement.parentElement.id].getOption();
                let halfAggregateInterval = option.aggregateIntervalMinutes * 60000 / 2;
                let from = moment(params[0].axisValue - halfAggregateInterval).format("D.M.YYYY, H:mm:ss");
                let to = moment(params[0].axisValue + halfAggregateInterval).format("H:mm:ss");
                let tooltipHTML = '<table><tr><td colspan="2" style="font-size: x-small;">' + from + " - " + to + '</td></tr>';
                params.forEach(item => {
                    let decimals = option.series[item.seriesIndex].decimals;
                    let unitLabel = option.series[item.seriesIndex].unitLabel;
                    tooltipHTML += ('<tr style="font-size: small;"><td>' + item.marker + item.seriesName + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + format(item.data[1], decimals) + unitLabel + '</td></tr>');
                });
                return tooltipHTML + '</table>';
            }
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
            name: yAxisName,
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
        series: series
    }

}

let noReadingString = "--";
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

function getDecimalSeparator(locale) {
    let n = 1.1;
    n = n.toLocaleString(locale).substring(1, 2);
    return n;
}
