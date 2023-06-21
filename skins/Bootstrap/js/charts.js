const BG_REGEX = /background-color:.*;/;
const DAY_NIGHT_KEY = "dayNight_";
const BAR = "bar";
const LINE = "line";

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

            let plotType = chart.weewxData.aggregate_interval_minutes !== undefined && category.plotType === undefined ? "bar" : category.plotType == undefined ? LINE : category.plotType;
            let aggregateType = chart.weewxData.aggregate_interval_minutes !== undefined && category.aggregateType === undefined ? SUM : category.aggregateType;
            let aggregateInterval = chart.weewxData.aggregate_interval_minutes !== undefined ? chart.weewxData.aggregate_interval_minutes * 60 : category.aggregateInterval;

            let dataReferences = undefined ? undefined : category.dataReferences;
            if (dataReferences !== undefined && !Array.isArray(dataReferences)) {
                dataReferences = [dataReferences];
            }

            let chartSeriesConfig = {
                name: decodeHtml(weewxData.labels.Generic[categoryId]),
                plotType: plotType,
                dataReferences: dataReferences === undefined ? [] : dataReferences,
                yAxisIndex: category.yAxisIndex === undefined ? 0 : category.yAxisIndex,
                aggregateType: aggregateType,
                aggregateInterval: aggregateInterval,
                payloadKey: category.payload_key,
                showTooltipValueNone: getBooleanOrDefault(category.showTooltipValueNone, plotType === BAR ? true : false),
                obs_group: category.obs_group,
                weewxColumn: categoryId,
                decimals: Number(category.decimals),
                showMaxMarkPoint: getBooleanOrDefault(category.showMaxMarkPoint, false),
                showMinMarkPoint: getBooleanOrDefault(category.showMinMarkPoint, false),
                showAvgMarkLine: getBooleanOrDefault(category.showAvgMarkLine, false),
                lineColor: category.lineColor,
                data: weewxData[categoryId],
                unit: weewxData.units.Labels[category.target_unit],
                symbol: category.symbol,
                symbolSize: category.symbolSize,
                chartId: chartId,
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
        chartOption = getChartOption(chartSeriesConfigs);
        for (let serie of chartOption.series) {
            let currenStart = serie.data[0][0] - chart.weewxData.aggregate_interval_minutes * 60000;
            let currentEnd = serie.data[serie.data.length - 1][0] + chart.weewxData.aggregate_interval_minutes * 60000;
            start = start === undefined || start >= currenStart ? currenStart : start;
            end = end === undefined || end <= currentEnd ? currentEnd : end;
        }

        chartSeriesConfigs.push(getDayNightSeries(chartOption, chartId, start, end));

        chartOption.animation = chart.weewxData.animation === undefined || !chart.weewxData.animation.toLowerCase() === "false";
        chart.setOption(chartOption);
        chartElement.appendChild(getTimestampDiv(documentChartId, timestamp));
    }
}

function getBooleanOrDefault(value, defaultValue) {
    return value === undefined ? defaultValue : value.toLowerCase() === 'true';
}

function getDayNightSeries(chartOption, chartId, start, end) {
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

    chartOption.series[0].markArea = getDayNightMarkArea();

    return {
        name: DAY_NIGHT_KEY + chartId,
        data: data,
    }
}


function getChartOption(seriesConfigs) {
    let series = [];
    let colors = [];
    let yAxisIndices = [];
    for (let seriesConfig of seriesConfigs) {
        if (seriesConfig.plotType === "scatter" && seriesConfig.dataReferences.length < 1) {
            continue;
        }
        getSeriesConfig(seriesConfig, series, colors);
        yAxisIndices[seriesConfig.yAxisIndex] = seriesConfig.yAxisIndex;
        yAxisIndices[seriesConfig.yAxisIndex]["unit"] = seriesConfig.unit;
        yAxisIndices[seriesConfig.yAxisIndex]["obs_group"] = seriesConfig.obs_group;
    }

    let yAxis = [];
    for (let yAxisIndex of Object.keys(yAxisIndices)) {
        let obs_group = yAxisIndices[yAxisIndex]["obs_group"]
        let yAxisItem = {
            name: yAxisIndices[yAxisIndex]["unit"],
            type: "value",
            minInterval: undefined,
            nameTextStyle: {
                fontWeight: 'bold',
            },
            axisLabel: {
                formatter: "{value}"
            },
            scale: true,
        };
        if (obs_group === "group_speed" || obs_group === "group_distance") {
            yAxisItem.min = 0;
        }
        if (obs_group === "group_percent") {
            yAxisItem.min = 0;
            yAxisItem.max = 100;
        }
        /*if (chart.weewxData.yAxis_minInterval !== undefined) {
            yAxisItem.minInterval = Number(chart.weewxData.yAxis_minInterval);
        }
        if (chart.weewxData.yAxis_axisLabel_align !== undefined) {
            yAxisItem.axisLabel.align = chart.weewxData.yAxis_axisLabel_align;
        }*/
        if (obs_group === "group_direction") {
            yAxisItem.min = 0;
            yAxisItem.max = 360;
            yAxisItem.minInterval = 90;
            yAxisItem.maxInterval = 90;
        }
        yAxis.push(yAxisItem);
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
        tooltip: getTooltip(seriesConfigs),
        /*label: {
            align: 'left'
        },*/
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
        yAxis: yAxis,
        series: series
    }
}

function getTooltip(seriesConfigs) {
    for (let seriesConfig of seriesConfigs) {
        if (seriesConfig.plotType === "scatter") {
            return;
        }
    }
    return {
        trigger: "axis",
        axisPointer: {
            type: LINE
        },
        show: true,
        position: "inside",
        formatter: function (params, ticket, callback) {
            let tooltipHTML = '<table>';
            let show = true;
            let marker = params[0].marker;
            let itemIndex = params[0].seriesIndex;
            let axisValue = params[0].axisValue;
            let intervals = [];
            for (let i = 0; i < seriesConfigs.length; i++) {
                let seriesItem = seriesConfigs[i];
                if (seriesItem.name.startsWith(DAY_NIGHT_KEY)) {
                    continue;
                }
                let unitString = seriesItem.unit === undefined ? "" : seriesConfigs[i].unit;
                let aggregateInterval = seriesItem.aggregateInterval;
                intervals.push(aggregateInterval);

                let formattedValue = "-";
                let dataValue = getDataValue(axisValue, seriesItem.data);
                if (dataValue === undefined && !seriesItem.showTooltipValueNone) {
                    continue;
                }
                if (aggregateInterval !== undefined) {
                    let halfAggregateInterval = aggregateInterval * 1000 / 2;
                    let aggregateAxisValue = params[0].axisValue;
                    if (dataValue === undefined) {
                        aggregateAxisValue = getAggregateAxisValue(params[0].axisValue, seriesItem.data, halfAggregateInterval);
                        dataValue = getDataValue(aggregateAxisValue, seriesItem.data);
                    }
                    let fromDate = new Date(aggregateAxisValue - halfAggregateInterval);
                    let toDate = new Date(aggregateAxisValue + halfAggregateInterval);
                    let from = fromDate.toLocaleDateString(localeWithDash) + ", " + fromDate.toLocaleTimeString(localeWithDash);
                    let to = toDate.toLocaleTimeString(localeWithDash);
                    if (i == 0 || aggregateInterval !== intervals[i - 1]) {
                        tooltipHTML += '<tr><td colspan="2" style="font-size: x-small;">' + from + " - " + to + '</td></tr>';
                    }
                } else {
                    let date = new Date(params[0].axisValue);
                    if (i == 0 || aggregateInterval !== intervals[i - 1]) {
                        tooltipHTML += '<tr><td colspan="2" style="font-size: x-small;">' + date.toLocaleDateString(localeWithDash) + ", " + date.toLocaleTimeString(localeWithDash) + '</td></tr>';
                    }
                }

                if (dataValue !== undefined && dataValue !== null) {
                    formattedValue = format(dataValue, seriesItem.decimals) + unitString;
                }
                tooltipHTML += ('<tr style="font-size: small;"><td>' + marker.replace(BG_REGEX, "background-color:" + seriesItem.lineColor + ";") + seriesItem.name + '</td><td style="text-align: right; padding-left: 10px; font-weight: bold;">' + formattedValue + '</td></tr>');

            }
            return show ? tooltipHTML + '</table>' : "";
        }
    }
}

function getDataValue(axisValue, data) {
    for (let item of data) {
        if (item[0] === axisValue) {
            return item[1];
        }
    }
    return undefined;
}

function getAggregateAxisValue(axisValue, data, halfAggregateInterval) {
    if (data.length < 1) {
        return;
    }
    let aggregateAxisValue = data[0][0];
    let diff = Math.abs(axisValue - aggregateAxisValue);
    for (let item of data) {
        if (diff < halfAggregateInterval) {
            return aggregateAxisValue;
        } else {
            aggregateAxisValue = item[0];
            if (diff != halfAggregateInterval || aggregateAxisValue == data[0][0]) {
                diff = Math.abs(axisValue - aggregateAxisValue);
            } else {
                diff = 0;
            }
        }
    }
    return aggregateAxisValue;
}

function getSeriesConfig(seriesConfig, series, colors) {
    colors.push(seriesConfig.lineColor);
    if (seriesConfig.data === undefined) {
        seriesConfig.data = [];
    }
    let type = seriesConfig.plotType;
    if (seriesConfig.aggregateInterval !== undefined) {
        seriesConfig.data = aggregate(seriesConfig)
    }
    let serie = {
        name: decodeHtml(seriesConfig.name),
        payloadKey: seriesConfig.payloadKey,
        weewxColumn: seriesConfig.weewxColumn,
        unit: seriesConfig.unit,
        decimals: seriesConfig.decimals,
        type: type,
        barWidth: '100%', //only applies to barchart
        barGap: '-100%', //only applies to barchart
        symbol: seriesConfig.symbol === undefined ? 'none' : seriesConfig.symbol,
        lineStyle: {
            width: seriesConfig.lineStyle === undefined || seriesConfig.lineStyle.width === undefined ? 1 : seriesConfig.lineStyle.width,
        },
        data: seriesConfig.data,
        yAxisIndex: seriesConfig.yAxisIndex,
    };

    if (seriesConfig.plotType === "scatter") {
        let groups = [weewxData.units.Groups[seriesConfig.obs_group]];
        let decimals = [seriesConfig.decimals];
        for (let dataReference of seriesConfig.dataReferences) {
            serie.name = weewxData.labels.Generic[dataReference] + " / " + serie.name;
            groups.push(weewxData.units.Groups[weewxData.charts[seriesConfig.chartId][dataReference].obs_group]);
            decimals.push(weewxData.charts[seriesConfig.chartId][dataReference].decimals);
            for (let i = 0; i < seriesConfig.data.length; i++) {
                let entry = seriesConfig.data[i];
                for (let referencedData of weewxData[dataReference]) {
                    if (referencedData[0] === entry[0]) {
                        entry.push(referencedData[1]);
                    }
                }
            }
        }

        serie.symbolSize = function (data) {
            return 5 * Math.sqrt(data[2] / Math.PI);
        };
        serie.emphasis = {
            focus: 'series',
            label: {
                show: true,
                formatter: function (param) {
                    //let date = new Date(param.data[0]);
                    let value = "";
                    for (let i = 0; i < seriesConfig.dataReferences.length; i++) {
                        value += format(param.data[i + 2], decimals[i + 1]) + weewxData.units.Labels[groups[i + 1]]
                    }

                    return value + " / " + format(param.data[1], decimals[0]) + weewxData.units.Labels[groups[0]];
                },
                position: 'top'
            }
        }
    }

    seriesConfig.serie = serie;


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
                    formatter: "{c}" + seriesConfig.unit
                }
            }
            ]
        };
    }

    series.push(serie);
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
            setAggregatedChartEntry(entry[1], entry[0] - Number(weewxData.config.archive_interval) * 1000, seriesConfig.aggregateInterval, aggregatedData);
        }
    }
    if (seriesConfig.aggregateType === AVG && aggregatedData.length > 0) {
        for (let entry of aggregatedData) {
            if (entry[2] !== 0) {
                entry[1] = entry[1] / entry[2];
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

function getDayNightMarkArea() {
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

function showToolbox(chartDiv) {
    /*charts[chartDiv.id].getOption().toolbox[0].show = true;
    console.log("toolbox " + charts[chartDiv.id].getOption().toolbox[0].show);*/
}

function hideToolbox(chartDiv) {
    /*charts[chartDiv.id].getOption().toolbox[0].show = false;
    console.log("toolbox " + charts[chartDiv.id].getOption().toolbox[0].show);*/
}