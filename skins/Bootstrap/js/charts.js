let baseColor = '#111111';
let backGroundColor = baseColor + '0a';
let nightBackGroundColorModifier = '1a';

function loadCharts() {
    for (let chartId of Object.keys(weewxData.charts)) {
        let documentChartId = chartId + "Chart";

        if (charts[documentChartId] !== undefined) {
            charts[documentChartId].dispose();
            charts[documentChartId] = undefined;
        }

        let chartElement = document.getElementById(documentChartId);
        if (chartElement === null || chartElement === undefined) {
            continue;
        }
        let chart = echarts.init(chartElement, null, { locale: eChartsLocale });
        chart.weewxData = weewxData.charts[chartId];
        charts[documentChartId] = chart;
        let chartSeriesConfigs = [];

        let timestamp = 0;

        for (let categoryId of Object.keys(weewxData.charts[chartId])) {
            let category = weewxData.charts[chartId][categoryId];
            if (typeof category !== 'object' || category === null) {
                continue;
            }
            chart.weewxData[categoryId].observationType = categoryId;
            addUndefinedIfCurrentMissing(weewxData[categoryId]);
            var obs_group = category.obs_group;
            let chartSeriesConfig = {
                name: decodeHtml(weewxData.labels.Generic[categoryId]),
                plotType: category.plotType,
                aggregateType: category.aggregateType,
                aggregateInterval: category.aggregateInterval,
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
            if (category.lineWidth !== undefined) {
                chartSeriesConfig.lineStyle = {
                    width: category.lineWidth,
                };
            }
            chartSeriesConfigs.push(chartSeriesConfig);

            if (weewxData[categoryId] !== undefined && weewxData[categoryId].length > 1) {
                let categoryTimestamp = weewxData[categoryId].slice(-2, -1)[0][0];
                if (categoryTimestamp !== undefined && categoryTimestamp > timestamp) {
                    timestamp = categoryTimestamp;
                }
            }
        }

        let chartOption;
        let start;
        let end;
        if (chart.weewxData.aggregate_interval_minutes !== undefined) {
            chartOption = getBarChartOption(chartSeriesConfigs, chart.weewxData.aggregate_interval_minutes);
            start = chartOption.series[0].data[0][0] - chart.weewxData.aggregate_interval_minutes * 60000;
            end = chartOption.series[0].data[chartOption.series[0].data.length - 1][0] + chart.weewxData.aggregate_interval_minutes * 60000;
        } else {
            chartOption = getLineChartOption(chartSeriesConfigs);
        }

        chartSeriesConfigs.push(getDayNightSeries(chartId, start, end));

        chartOption.series[0].markArea = getMarkArea();

        chartOption.yAxis.scale = true;
        if (obs_group === "group_speed") {
            chartOption.yAxis.min = 0;
        }
        if (obs_group === "group_percent") {
            chartOption.yAxis.min = 0;
            chartOption.yAxis.max = 100;
        }
        if (chart.weewxData.yAxis_minInterval !== undefined) {
            chartOption.yAxis.minInterval = Number(chart.weewxData.yAxis_minInterval);
        }
        if (chart.weewxData.yAxis_axisLabel_align !== undefined) {
            chartOption.yAxis.axisLabel.align = chart.weewxData.yAxis_axisLabel_align;
        }
        if (obs_group === "group_direction") {
            chartOption.yAxis.min = 0;
            chartOption.yAxis.max = 360;
            chartOption.yAxis.minInterval = 90;
            chartOption.yAxis.maxInterval = 90;
        }
        chartOption.animation = chart.weewxData.animation === undefined || !chart.weewxData.animation.toLowerCase() === "false";
        chart.setOption(chartOption);
        chartElement.appendChild(getTimestampDiv(documentChartId, timestamp));
    }
}

function getDayNightSeries(chartId, start, end) {
    let data = [];

    if (weewxData['day_night_events'] === undefined) {
        return data;
    }

    weewxData['day_night_events'].forEach(
        (element, index) => {
            data.push([element[0], undefined]);
        }
    );
    if (start !== undefined && data[0] !== undefined) {
        data[0][0] = start;
    }
    if (end !== undefined && data[data.length - 1] !== undefined) {
        data[data.length - 1][0] = end;
    }

    return {
        name: "dayNight_" + chartId,
        data: data
    }
}


function getLineChartOption(seriesConfigs) {
    let yAxisName = seriesConfigs[0].unit;
    let series = [];
    let colors = [];
    let configs = seriesConfigs;
    for (let seriesConfig of seriesConfigs) {
        getSeriesConfig(seriesConfig, yAxisName, series, colors, undefined);
    }

    return {
        legend: {
            type: "plain"
        },
        textStyle: {
            fontSize: 10,
        },
        color: colors,
        backgroundColor: backGroundColor,
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
                    let unitString = configs[item.seriesIndex].unit === undefined ? "" : configs[item.seriesIndex].unit;
                    if (!isNaN(item.data[1])) {
                        show = true;
                        tooltipHTML += ('<tr style="font-size: small;"><td>' + item.marker + item.seriesName + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + format(item.data[1], configs[item.seriesIndex].decimals) + unitString + '</td></tr>');
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

function getSeriesConfig(seriesConfig, yAxisName, series, colors, aggregateIntervalMinutes) {
    colors.push(seriesConfig.lineColor);
    if (seriesConfig.data === undefined) {
        seriesConfig.data = [];
    }
    let type = seriesConfig.plotType;
    /* Begin Legacy Support */
    if(type === undefined && aggregateIntervalMinutes !== undefined) {
        type = "bar";
        seriesConfig.aggregateInterval = aggregateIntervalMinutes * 60;
    }
    if(type === undefined) {
        type = "line";
    }
    /* End Legacy Support */
    if(seriesConfig.aggregateInterval !== undefined) {
        seriesConfig.data = aggregate(seriesConfig)
    }
    let serie = {
        name: decodeHtml(seriesConfig.name),
        payloadKey: seriesConfig.payloadKey,
        weewxColumn: seriesConfig.weewxColumn,
        type: type,
        barWidth: '100%', //only applies to barchart
        barGap: '-100%', //only applies to barchart
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

function getBarChartOption(seriesConfigs, aggregateIntervalMinutes) {
    let yAxisName = seriesConfigs[0].unit;
    let series = [];
    let colors = [];
    let configs = seriesConfigs;
    for (let seriesConfig of seriesConfigs) {
        getSeriesConfig(seriesConfig, yAxisName, series, colors, aggregateIntervalMinutes);
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
        backgroundColor: backGroundColor,
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
                let halfAggregateInterval = aggregateIntervalMinutes * 60000 / 2;
                let fromDate = new Date(params[0].axisValue - halfAggregateInterval);
                let toDate = new Date(params[0].axisValue + halfAggregateInterval);
                let from = fromDate.toLocaleDateString(localeWithDash) + ", " + fromDate.toLocaleTimeString(localeWithDash);
                let to = toDate.toLocaleTimeString(localeWithDash);
                let tooltipHTML = '<table><tr><td colspan="2" style="font-size: x-small;">' + from + " - " + to + '</td></tr>';
                params.forEach(item => {
                    let unitString = configs[item.seriesIndex].unit === undefined ? "" : configs[item.seriesIndex].unit;
                    tooltipHTML += ('<tr style="font-size: small;"><td>' + item.marker + item.seriesName + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + format(item.data[1], configs[item.seriesIndex].decimals) + unitString + '</td></tr>');
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

function aggregate(seriesConfig) {
    let aggregatedData = [];
    for (let entry of seriesConfig.data) {
        //timestamp needs to be shifted one archive_interval to show the readings in the correct time window
        if (entry[1] !== undefined) {
            setAggregatedChartEntry(entry[1], entry[0] - Number(weewxData.config.archive_interval) * 1000, seriesConfig, aggregatedData);
        }
    }
    if(seriesConfig.aggregateType === "avg" && aggregatedData.length > 0) {
        for (let entry of aggregatedData) {
            if(entry[2] !== 0) {
                entry[1] = entry[1]/entry[2];
            }
        }
    }
    return aggregatedData;
}

function getXMinInterval() {
    return weewxData.config.timespan * 3600000 / 8;
}

function addUndefinedIfCurrentMissing(data) {
    let latestTimestamp = 0;
    if (data.length > 0) {
        latestTimestamp = data[data.length - 1][0];
    }
    if (Date.now() - latestTimestamp > weewxData.config.archive_interval) {
        data.push([Date.now(), undefined]);
    }
}

function getTimestampDiv(parentId, timestamp) {
    let outerDiv = document.createElement("div");
    outerDiv.setAttribute("class", "chartTimestampOuter");
    let timestampDiv = document.createElement("div");
    timestampDiv.id = parentId + "_timestamp";
    timestampDiv.setAttribute("class", "chartTimestamp");
    if (timestamp > 0) {
        timestampDiv.innerHTML = formatDateTime(timestamp);
    }
    outerDiv.appendChild(timestampDiv);
    return outerDiv;
}

function getMarkArea() {
    let dayNightEvents = weewxData['day_night_events'];
    let data = [];
    if (dayNightEvents === undefined) {
        return data;
    }
    dayNightEvents.forEach(
        (element, index) => {
            let last = dayNightEvents[index + 1];
            let start = index == 0 ? undefined : element[0];
            let end = index == (dayNightEvents.length - 1) ? undefined : last[0];
            let extentEnd = last !== undefined ? last[1] : element[1];
            let part = getPart(start, end, element[1], extentEnd);
            data.push(part);

        }
    );

    return {
        data: data,
        silent: true
    }
}



function getPart(start, end, startDarkeningExtent, endDarkeningExtent) {
    return [
        {
            itemStyle: {
                color: {
                    type: 'linear',
                    x: 0,
                    y: 0,
                    x2: 1,
                    y2: 0,
                    colorStops: [{
                        offset: 0, color: baseColor + getColorModifier(startDarkeningExtent)
                    }, {
                        offset: 1, color: baseColor + getColorModifier(endDarkeningExtent)
                    }],
                    global: false
                }
            },
            xAxis: start
        },
        {
            xAxis: end
        }
    ];
}

function getColorModifier(extent) {
    return Math.round(
        Number('0x' + nightBackGroundColorModifier) * extent
    ).toString(16).padStart(2, '0');
}