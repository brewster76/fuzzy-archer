for(let chartId of Object.keys(weewxData.charts)) {
    let documentChartId = chartId + "Chart";
    let chartElement = document.getElementById(documentChartId);
    if(chartElement === null || chartElement === undefined) {
        continue;
    }
    let chart = echarts.init(chartElement, null, {locale: eChartsLocale});
    chart.weewxData = weewxData.charts[chartId];
    charts[documentChartId] = chart;
    let chartSeriesConfigs = [];

    let timestamp = 0;

    for(let categoryId of Object.keys(weewxData.charts[chartId])) {
        let category = weewxData.charts[chartId][categoryId];
        if(typeof category !== 'object' || category === null) {
            continue;
        }
        chart.weewxData[categoryId].observationType = categoryId;
        addUndefinedIfCurrentMissing(weewxData[categoryId]);
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

        if (weewxData[categoryId] !== undefined && weewxData[categoryId].length > 1) {
            let categoryTimestamp = weewxData[categoryId].slice(-2, -1)[0][0];
            if(categoryTimestamp !== undefined && categoryTimestamp > timestamp) {
                timestamp = categoryTimestamp;
            }
        }
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
    if(chart.weewxData.yAxis_minInterval !== undefined) {
        chartOption.yAxis.minInterval = Number(chart.weewxData.yAxis_minInterval);
    }
    if(chart.weewxData.yAxis_axisLabel_align !== undefined) {
        chartOption.yAxis.axisLabel.align = chart.weewxData.yAxis_axisLabel_align;
    }
    if(obs_group === "group_direction") {
        chartOption.yAxis.min = 0;
        chartOption.yAxis.max = 360;
        chartOption.yAxis.minInterval = 90;
        chartOption.yAxis.maxInterval = 90;
    }
    chartOption.animation = chart.weewxData.animation === undefined || !chart.weewxData.animation.toLowerCase() === "false";
    chart.setOption(chartOption);
    chartElement.appendChild(getTimestampDiv(documentChartId, timestamp));
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
            position: "inside",
            formatter: function (params, ticket, callback) {
                let date = new Date(params[0].axisValue);
                let tooltipHTML = '<table><tr><td colspan="2" style="font-size: x-small;">' + date.toLocaleDateString(localeWithDash) + ", " + date.toLocaleTimeString(localeWithDash) + '</td></tr>';
                let show = false;
                params.forEach(item => {
                    if(!isNaN(item.data[1])) {
                        show = true;
                        tooltipHTML += ('<tr style="font-size: small;"><td>' + item.marker + item.seriesName + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + format(item.data[1], configs[item.seriesIndex].decimals) + configs[item.seriesIndex].unit + '</td></tr>');
                    }
                });
                return show ? tooltipHTML + '</table>' : "";
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
            position: "inside",
            formatter: function (params, ticket, callback) {
                let halfAggregateInterval = aggregateInterval * 60000 / 2;
                let fromDate = new Date(params[0].axisValue - halfAggregateInterval);
                let toDate = new Date(params[0].axisValue + halfAggregateInterval);
                let from = fromDate.toLocaleDateString(localeWithDash) + ", " + fromDate.toLocaleTimeString(localeWithDash);
                let to = toDate.toLocaleTimeString(localeWithDash);
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
        if(entry[1] !== undefined){
            setAggregatedChartEntry(entry[1], entry[0] - Number(weewxData.config.archive_interval) * 1000, aggregateIntervalMinutes, aggregatedData);
        }
    }
    return aggregatedData;
}

function getXMinInterval() {
    return weewxData.config.timespan * 3600000 / 8;
}

function addUndefinedIfCurrentMissing(data) {
    let latestTimestamp = 0;
    if(data.length > 0) {
        latestTimestamp = data[data.length - 1][0];
    }
    if(Date.now() - latestTimestamp > weewxData.config.archive_interval) {
        data.push([Date.now(), undefined]);
    }
}

function getTimestampDiv(parentId, timestamp) {
    let outerDiv = document.createElement("div");
    outerDiv.setAttribute("class", "chartTimestampOuter");
    let timestampDiv = document.createElement("div");
    timestampDiv.id = parentId + "_timestamp";
    timestampDiv.setAttribute("class", "chartTimestamp");
    if(timestamp > 0) {
        timestampDiv.innerHTML = formatDateTime(timestamp);
    }
    outerDiv.appendChild(timestampDiv);
    return outerDiv;
}