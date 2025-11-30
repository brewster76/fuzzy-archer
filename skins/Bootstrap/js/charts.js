const BG_REGEX = /background-color:.*;/;
const DAY_NIGHT = "dayNight";
const DAY_NIGHT_KEY = DAY_NIGHT + "_";
const BAR = "bar";
const LINE = "line";
const SCATTER = "scatter";

let baseColor = '#111111';
let backGroundColor = baseColor + '0a';
let nightBackGroundColorModifier = '1a';

function loadCharts() {
    for (let chartId of Object.keys(weewxData.charts)) {
        let documentChartId = chartId + CHART;

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

            let plotType = category.plotType == undefined ? LINE : category.plotType;
            let aggregateType = category.aggregateType === undefined ? SUM : category.aggregateType;
            let aggregateInterval = category.aggregateInterval;

            let dataReferences = undefined ? undefined : category.dataReferences;
            if (dataReferences !== undefined && !Array.isArray(dataReferences)) {
                dataReferences = [dataReferences];
            }
            let seriesName = category.seriesName === undefined ? weewxData.labels.Generic[categoryId] : category.seriesName;
            let chartSeriesConfig = {
                name: decodeHtml(seriesName),
                plotType: plotType,
                dataReferences: dataReferences === undefined ? [] : dataReferences,
                yAxisIndex: category.yAxisIndex === undefined ? 0 : category.yAxisIndex,
                aggregateType: aggregateType,
                aggregateInterval: aggregateInterval,
                payloadKey: category.payload_key,
                labelFontSize: category.labelFontSize === undefined ? 11 : category.labelFontSize,
                showTooltipValueNone: getBooleanOrDefault(category.showTooltipValueNone, plotType === BAR ? true : false),
                obs_group: category.obs_group,
                weewxColumn: categoryId,
                decimals: Number(category.decimals),
                interval: category.interval,
                minInterval: category.minInterval,
                maxInterval: category.maxInterval,
                splitNumber: category.splitNumber,
                showMaxMarkPoint: getBooleanOrDefault(category.showMaxMarkPoint, false),
                showMinMarkPoint: getBooleanOrDefault(category.showMinMarkPoint, false),
                showAvgMarkLine: getBooleanOrDefault(category.showAvgMarkLine, false),
                lineColor: category.lineColor,
                data: weewxData[categoryId],
                unit: weewxData.units.Labels[category.target_unit],
                symbol: category.symbol,
                symbolSize: category.symbolSize === undefined ? 4 : category.symbolSize,
                chartId: chartId,
            }
            if (category.lineWidth !== undefined) {
                chartSeriesConfig.lineStyle = {
                    width: category.lineWidth,
                };
            }
            chartSeriesConfigs.push(chartSeriesConfig);

            if (weewxData[categoryId] !== undefined && weewxData[categoryId] !== null && weewxData[categoryId].length > 1) {
                let categoryTimestamp = weewxData[categoryId].slice(-1)[0][0];
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
            if (serie.data === undefined || serie.data === null) {
                continue;
            }
            let currenStart = serie.data[0][0] - archiveIntervalSeconds * 1000;
            let currentEnd = serie.data[serie.data.length - 1][0] + archiveIntervalSeconds * 1000;
            start = start === undefined || start >= currenStart ? currenStart : start;
            end = end === undefined || end <= currentEnd ? currentEnd : end;
        }

        chartSeriesConfigs.push(getDayNightSeries(chartOption, chartId, start, end));

        chartOption.animation = chart.weewxData.animation === undefined || !chart.weewxData.animation.toLowerCase() === "false";
        chartOption.textStyle = {
            fontSize: chart.weewxData.fontSize === undefined ? 10 : chart.weewxData.fontSize,
        };
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

    let dayNightSerie = {
        "name": DAY_NIGHT,
        "type": "line",
        "data": [[start, undefined], [end, undefined]],
        "markArea": getDayNightMarkArea(),
    }

    chartOption.series.push(dayNightSerie);

    return {
        name: DAY_NIGHT_KEY + chartId,
        data: data,
    }
}


function getChartOption(seriesConfigs) {
    let series = [];
    let colors = [];
    let yAxisIndices = [];
    let legendData = [];
    let z = seriesConfigs.length;
    for (let seriesConfig of seriesConfigs) {
        if (seriesConfig.plotType === SCATTER && seriesConfig.dataReferences.length < 1) {
            continue;
        }
        getSeriesConfig(seriesConfig, series, colors, z--);
        yAxisIndices[seriesConfig.yAxisIndex] = Array();
        yAxisIndices[seriesConfig.yAxisIndex]["unit"] = seriesConfig.unit;
        yAxisIndices[seriesConfig.yAxisIndex]["obs_group"] = seriesConfig.obs_group;
        yAxisIndices[seriesConfig.yAxisIndex]["decimals"] = seriesConfig.decimals;
        yAxisIndices[seriesConfig.yAxisIndex]["interval"] = seriesConfig.interval;
        yAxisIndices[seriesConfig.yAxisIndex]["minInterval"] = seriesConfig.minInterval;
        yAxisIndices[seriesConfig.yAxisIndex]["maxInterval"] = seriesConfig.maxInterval;
        yAxisIndices[seriesConfig.yAxisIndex]["splitNumber"] = seriesConfig.splitNumber;
        yAxisIndices[seriesConfig.yAxisIndex]["labelFontSize"] = seriesConfig.labelFontSize;
    }

    for (let serie of series) {
        if (serie.name.startsWith(DAY_NIGHT_KEY)) {
            continue;
        }
        let legendItem = {
            name: serie.name
        }
        if (serie.symbol !== undefined && serie.symbol !== 'none') {
            legendItem.icon = serie.symbol;
        }
        legendData.push(legendItem);
    }

    let yAxis = [];
    for (let yAxisIndex of Object.keys(yAxisIndices)) {
        let obs_group = yAxisIndices[yAxisIndex]["obs_group"];
        let unit = yAxisIndices[yAxisIndex]["unit"];
        let decimals = yAxisIndices[yAxisIndex]["decimals"];
        let interval = yAxisIndices[yAxisIndex]["interval"];
        let minInterval = yAxisIndices[yAxisIndex]["minInterval"];
        let maxInterval = yAxisIndices[yAxisIndex]["maxInterval"];
        let splitNumber = yAxisIndices[yAxisIndex]["splitNumber"];
        let yAxisItem = {
            name: Array.isArray(unit) && unit.length > 1 ? unit[1] : unit,
            type: "value",
            alignTicks: true,
            interval: interval,
            minInterval: minInterval,
            maxInterval: maxInterval,
            splitNumber: splitNumber,
            nameTextStyle: {
                fontWeight: 'bold',
            },
            axisLabel: {
                formatter: function (value, index) {
                    let formattedValue = format(value, decimals);
                    if (value * Math.pow(10, decimals) % 1 != 0) {
                        formattedValue = "";
                    }
                    if (value >= 1000) {
                        formattedValue = value.toFixed();
                        if (value % 1 != 0) {
                            formattedValue = "";
                        }
                    }
                    return formattedValue;
                },
                fontSize: yAxisIndices[yAxisIndex]["labelFontSize"]
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
            type: "plain",
            top: 10,
            data: legendData
        },
        color: colors,
        backgroundColor: backGroundColor,
        toolbox: {
            show: false,
            top: 10,
            feature: {
                dataZoom: {
                    yAxisIndex: "none"
                }
            }
        },
        tooltip: getTooltip(seriesConfigs),
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
            },
            axisLabel: {
                formatter: function (value, idx) {
                    let day = luxon.DateTime.fromMillis(value, { zone: stationTimezone }).startOf('day').toMillis();
                    if (value === day) {
                        return `{day|${formatDate(value, stationTimezone, { day: 'numeric' })}}`;
                    } else {
                        return formatTime(value, stationTimezone, luxon.DateTime.TIME_24_SIMPLE);
                    }
                },
                rich: {
                    day: {
                        fontSize: '10px',
                        fontWeight: 'bold'
                    }
                }
            },
        },
        yAxis: yAxis,
        series: series
    }
}

function getTooltip(seriesConfigs) {
    let containsScatter = false;
    for (let seriesConfig of seriesConfigs) {
        if (seriesConfig.plotType === SCATTER) {
            containsScatter = true;
        }
    }
    return {
        trigger: containsScatter ? "item" : "axis",
        axisPointer: {
            type: LINE
        },
        show: true,
        position: containsScatter ? "top" : "inside",
        formatter: function (params, ticket, callback) {
            let seriesName = Array.isArray(params) ? params[0].seriesName : params.seriesName;
            if (seriesName.includes(DAY_NIGHT)) {
                return;
            }
            let tooltipHTML = '<table>';
            let show = true;
            let marker;
            let itemIndex;
            let axisValue;

            if (Array.isArray(params)) {
                marker = params[0].marker;
                itemIndex = params[0].seriesIndex;
                axisValue = params[0].axisValue;
            } else {
                marker = params.marker;
                itemIndex = params.seriesIndex;
                axisValue = params.data[0];
            }

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
                let dataValue;
                if (Array.isArray(params) && params[i] !== undefined && params[i]["data"] !== undefined) {
                    dataValue = params[i]["data"][1];
                } else {
                    dataValue = getDataValue(axisValue, seriesItem.data);
                }
                if (!Array.isArray(params) && params["data"][i + 1] !== undefined) {
                    dataValue = params["data"][i + 1];
                }
                if (dataValue === undefined && !seriesItem.showTooltipValueNone) {
                    continue;
                }
                let aggregateAxisValue = axisValue;
                if (aggregateInterval !== undefined) {
                    let halfAggregateInterval = aggregateInterval * 1000 / 2;

                    if (dataValue === undefined) {
                        aggregateAxisValue = getAggregateAxisValue(aggregateAxisValue, seriesItem.data, halfAggregateInterval);
                        dataValue = getDataValue(aggregateAxisValue, seriesItem.data);
                    }
                    let fromDate = new Date(aggregateAxisValue - halfAggregateInterval);
                    let toDate = new Date(aggregateAxisValue + halfAggregateInterval);
                    let from = formatDateTime(fromDate, stationTimezone);
                    let to = formatTime(toDate, stationTimezone);
                    if (i == 0 || aggregateInterval !== intervals[i - 1]) {
                        tooltipHTML += '<tr><td colspan="2" style="font-size: x-small;">' + from + " - " + to + '</td></tr>';
                    }
                } else {
                    let date = new Date(aggregateAxisValue);
                    if (i == 0 || aggregateInterval !== intervals[i - 1]) {
                        tooltipHTML += '<tr><td colspan="2" style="font-size: x-small;">' + formatDateTime(date, stationTimezone) + '</td></tr>';
                    }
                }

                if (dataValue !== undefined && dataValue !== null) {
                    let formattedDataValue = format(dataValue, seriesItem.decimals);
                    formattedValue = formattedDataValue + getUnitString(formattedDataValue, unitString);
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

function getSeriesConfig(seriesConfig, series, colors, z) {
    colors.push(seriesConfig.lineColor);
    if (seriesConfig.data === undefined) {
        seriesConfig.data = [];
    }
    let type = seriesConfig.plotType;
    if (seriesConfig.aggregateInterval !== undefined) {
        seriesConfig.data = aggregate(seriesConfig.data, seriesConfig.aggregateInterval, seriesConfig.aggregateType, seriesConfig.decimals);
    }
    let serie = {
        name: decodeHtml(seriesConfig.name),
        z: z,
        payloadKey: seriesConfig.payloadKey,
        weewxColumn: seriesConfig.weewxColumn,
        unit: seriesConfig.unit,
        decimals: seriesConfig.decimals,
        type: type,
        barWidth: '100%', //only applies to barchart
        barGap: '-100%', //only applies to barchart
        symbol: seriesConfig.symbol === undefined ? 'none' : seriesConfig.symbol,
        symbolKeepAspect: true,
        lineStyle: {
            width: seriesConfig.lineStyle === undefined || seriesConfig.lineStyle.width === undefined ? 1 : seriesConfig.lineStyle.width,
        },
        data: seriesConfig.data,
        yAxisIndex: seriesConfig.yAxisIndex,
    };


    if (seriesConfig.symbolSize !== undefined) {
        serie.symbolSize = new Function("return " + seriesConfig.symbolSize)();
    }

    if (seriesConfig.plotType === SCATTER) {
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
                        if (referencedData[1] === 0 || referencedData[1] === null) {
                            entry[1] = null;
                        }
                    }
                }
            }
        }
        serie.emphasis = {
            focus: 'none',
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
        for (let dataPoint of weewxData[seriesConfig.weewxColumn + "_" + DAILY_HIGH_LOW_KEY]) {
            let name = DAILY_MAX;
            let position = "top";
            let value = dataPoint[1];
            let valueTimestamp = dataPoint[0];
            if (dataPoint[2] === "min") {
                name = DAILY_MIN;
                position = "bottom";
            }
            markPoint.data.push({
                coord: [valueTimestamp, value],
                name: name,
                label: {
                    show: true,
                    position: position,
                    formatter: format(value, seriesConfig.decimals).toString(),
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
                    formatter: function (value, ticket) {
                        value = format(value.data.value, seriesConfig.decimals);
                        return value + getUnitString(value, seriesConfig.unit);
                    }
                }
            }
            ]
        };
    }

    series.push(serie);
}

function getXMinInterval() {
    return weewxData.config.timespan * 3600000 / 8;
}

function addUndefinedIfCurrentMissing(data) {
    if (data === undefined || data === null) {
        return;
    }
    let latestTimestamp = 0;
    if (data.length > 0) {
        latestTimestamp = data[data.length - 1][0];
    }
    if (Date.now() - latestTimestamp > weewxData.config.archive_interval * 1000) {
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
        timestampDiv.innerHTML = formatDateTime(timestamp, stationTimezone);
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
