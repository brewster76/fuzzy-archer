let charts = {};
for(let chartId of Object.keys(weewxData.charts)) {
    let documentChartId = chartId + "Chart";
    let chart = echarts.init(document.getElementById(documentChartId));
    chart.weewxData = weewxData.charts[chartId];
    charts[documentChartId] = chart;
    let chartSeriesConfigs = [];
    for(let categoryId of Object.keys(weewxData.charts[chartId])) {
        let category = weewxData.charts[chartId][categoryId];
        if(typeof category !== 'object' || category === null) {
            continue;
        }
        chart.weewxData[categoryId].observationType = categoryId;
        var obs_group = category.obs_group;
        let chartSeriesConfig = {
            name: weewxData.labels.Generic[categoryId],
            payloadKey: category.payload_key,
            weewxColumn: categoryId,
            decimals: Number(category.decimals),
            showMaxMarkPoint: category.showMaxMarkPoint.toLowerCase() === 'true',
            showMinMarkPoint: category.showMinMarkPoint.toLowerCase() === 'true',
            showAvgMarkLine: category.showAvgMarkLine.toLowerCase() === 'true',
            lineColor: category.lineColor,
            data: weewxData[categoryId],
            unit: weewxData.units.Labels[category.target_unit],
            symbol: category.symbol,
            symbolSize: category.symbolSize,
        }
        if(category.lineWidth !== undefined) {
            chartSeriesConfig.lineStyle = {
                width: category.lineWidth,
            };
        }
        chartSeriesConfigs.push(chartSeriesConfig);
    }
    let chartOption;
    if(chart.weewxData.aggregate_interval_minutes !== undefined) {
        chartOption = getBarChartOption(chartSeriesConfigs, chart.weewxData.aggregate_interval_minutes);
    } else {
        chartOption = getLineChartOption(chartSeriesConfigs);
    }

    if(obs_group === "group_speed") {
        chartOption.yAxis.min = 0;
    }
    if(obs_group === "group_percent") {
        chartOption.yAxis.min = 0;
        chartOption.yAxis.max = 100;
    }
    if(obs_group === "group_direction") {
        chartOption.yAxis.min = 0;
        chartOption.yAxis.max = 360;
        chartOption.yAxis.minInterval = 90;
        chartOption.yAxis.maxInterval = 90;
    }
    chartOption.animation = chart.weewxData.animation === undefined || !chart.weewxData.animation.toLowerCase() === "false";
    chart.setOption(chartOption);
}

function getLineChartOption(seriesConfigs) {
    let yAxisName = seriesConfigs[0].unit;
    let series = [];
    let colors = [];
    let configs = seriesConfigs;
    for (let seriesConfig of seriesConfigs) {
        colors.push(seriesConfig.lineColor);
        if (seriesConfig.data === undefined) {
            seriesConfig.data = [];
        }
        let serie = {
            name: seriesConfig.name,
            payloadKey: seriesConfig.payloadKey,
            weewxColumn: seriesConfig.weewxColumn,
            type: "line",
            symbol: seriesConfig.symbol === undefined ? 'none' : seriesConfig.symbol,
            lineStyle: {
                width: seriesConfig.lineStyle === undefined || seriesConfig.lineStyle.width === undefined ? 1 : seriesConfig.lineStyle.width,
            },
            data: seriesConfig.data,
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
        color: colors,
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
                let tooltipHTML = '<table><tr><td colspan="2" style="font-size: x-small;">' + moment(params[0].axisValue).format("D.M.YYYY, H:mm:ss") + '</td></tr>';
                params.forEach(item => {
                    tooltipHTML += ('<tr style="font-size: small;"><td>' + item.marker + item.seriesName + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + format(item.data[1], configs[item.seriesIndex].decimals) + configs[item.seriesIndex].unit + '</td></tr>');
                });
                return tooltipHTML + '</table>';
            }
        },
        xAxis: {
            show: true,
            minInterval: getXMinInterval(),
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
            minInterval: undefined,
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

function getBarChartOption(seriesConfigs, aggregateIntervalMinutes) {
    let yAxisName = seriesConfigs[0].unit;
    let series = [];
    let colors = [];
    let configs = seriesConfigs;
    let aggregateInterval = aggregateIntervalMinutes
    for (let seriesConfig of seriesConfigs) {
        colors.push(seriesConfig.lineColor);
        if (seriesConfig.data === undefined) {
            seriesConfig.data = [];
        }
        let serie = {
            name: seriesConfig.name,
            payloadKey: seriesConfig.payloadKey,
            weewxColumn: seriesConfig.weewxColumn,
            type: "bar",
            barWidth: '100%',
            data: aggregate(seriesConfig.data, aggregateIntervalMinutes),
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
        color: colors,
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
                let halfAggregateInterval = aggregateInterval * 60000 / 2;
                let from = moment(params[0].axisValue - halfAggregateInterval).format("D.M.YYYY, H:mm:ss");
                let to = moment(params[0].axisValue + halfAggregateInterval).format("H:mm:ss");
                let tooltipHTML = '<table><tr><td colspan="2" style="font-size: x-small;">' + from + " - " + to + '</td></tr>';
                params.forEach(item => {
                    tooltipHTML += ('<tr style="font-size: small;"><td>' + item.marker + item.seriesName + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + format(item.data[1], configs[item.seriesIndex].decimals) + configs[item.seriesIndex].unit + '</td></tr>');
                });
                return tooltipHTML + '</table>';
            }
        },
        label: {
            align: 'left'
        },
        xAxis: {
            show: true,
            minInterval: getXMinInterval(),
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
            minInterval: undefined,
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

function getDecimalSeparator(locale) {
    let n = 1.1;
    n = n.toLocaleString(locale).substring(1, 2);
    return n;
}

function aggregate(data, aggregateIntervalMinutes) {
    let aggregatedData = [];
    for(let entry of data) {
        //timestamp needs to be shifted one archive_interval to show the readings in the correct time window
        setAggregatedChartEntry(entry[1], entry[0] - Number(weewxData.config.archive_interval) * 1000, aggregateIntervalMinutes, aggregatedData);
    }
    return aggregatedData;
}

function getXMinInterval() {
    return weewxData.config.timespan * 3600000 / 8;
}