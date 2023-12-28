const AVG = "avg";
const SUM = "sum";
const CHART = "Chart";
const CHARTS = "charts";

let weewxData;
let weewxDataUrl = "weewxData.json";
let stationInfoDataUrl = "reportData.json";
let gauges = {};
let charts = {};
let lastAsyncReloadTimestamp = Date.now();
let lastGoodStamp = lastAsyncReloadTimestamp / 1000;
let archiveIntervalSeconds;
let localeWithDash;
let lang;
let eChartsLocale;
let maxAgeHoursMS;
let intervalData = {};

fetch(weewxDataUrl, {
    cache: "no-store"
}).then(function (u) {
    return u.json();
}).then(function (serverData) {
    weewxData = serverData;
    archiveIntervalSeconds = weewxData.config.archive_interval;
    localeWithDash = locale.replace("_", "-");
    lang = locale.split("_")[0];
    eChartsLocale = lang.toUpperCase();
    maxAgeHoursMS = weewxData.config.timespan * 3600000;

    let clients = [];
    if (weewxData !== undefined && weewxData.config !== undefined && weewxData.config.MQTT !== undefined && weewxData.config.MQTT.connections !== undefined) {
        for (let connectionId of Object.keys(weewxData.config.MQTT.connections)) {
            let connection = weewxData.config.MQTT.connections[connectionId];
            let mqttConnection = connection.broker_connection;
            let mqttUsername = connection.mqtt_username;
            let mqttPassword = connection.mqtt_password;
            let intervalData = {};

            let mqttCredentials;
            if (mqttUsername !== undefined) {
                mqttCredentials = {
                    username: mqttUsername
                };
                if (mqttPassword !== undefined) {
                    mqttCredentials["password"] = mqttPassword;
                }
            }
            if (mqttCredentials === undefined) {
                client = mqtt.connect(mqttConnection);
            } else {
                client = mqtt.connect(mqttConnection, mqttCredentials);
            }
            client.topics = connection.topics;
            clients.push(client);

            for (let topic of Object.keys(connection.topics)) {
                client.subscribe(topic);
            }

            client.on("message", function (topic, payload) {
                console.log(topic);
                checkAsyncReload();
                let jPayload = {};
                let topicConfig = this.topics[topic];
                if (topicConfig.type.toUpperCase() === "JSON") {
                    jPayload = JSON.parse(payload);
                } else if (topicConfig.type.toLowerCase() === "plain" && topicConfig.payload_key !== undefined) {
                    jPayload[topicConfig.payload_key] = parseFloat(payload);
                } else {
                    return;
                }

                let timestamp;
                if (jPayload.dateTime !== undefined) {
                    timestamp = parseInt(jPayload.dateTime) * 1000;
                    if (Date.now() - timestamp > archiveIntervalSeconds * 1000) {
                        return;
                    }
                } else {
                    timestamp = Date.now();
                }
                let date = new Date(timestamp);
                for (let gaugeId of Object.keys(gauges)) {
                    let gauge = gauges[gaugeId];
                    let value = convert(gauge.weewxData, getValue(jPayload, gauge.weewxData.payload_key));
                    if (!isNaN(value)) {
                        setGaugeValue(gauge, value, timestamp);
                    }
                }
                for (let chartId of Object.keys(charts)) {
                    let chart = charts[chartId];
                    chart.chartId = chartId;
                    addValues(chart, jPayload, timestamp);
                }
                let lastUpdate = document.getElementById("lastUpdate");
                lastUpdate.innerHTML = formatDateTime(date);
            });
        }
    }
    if (typeof loadGauges === "function") {
        loadGauges();
    }
    if (typeof loadCharts === "function") {
        loadCharts();
    }
}).catch(err => {
    throw err
});

setInterval(checkAsyncReload, 60000);

function setGaugeValue(gauge, value, timestamp) {
    let option = gauge.getOption();
    let valueSeries = option.series[0];
    addValue(gauge.weewxData.dataset, value, timestamp);
    if (option.series[1] !== undefined) {
        option.series[1].axisLine.lineStyle.color = getHeatColor(valueSeries.max, valueSeries.min, valueSeries.splitNumber, valueSeries.axisTick.splitNumber, gauge.weewxData.dataset.data);
    }
    gauge.setOption(option);
    updateGaugeValue(value, gauge);
}

function updateGaugeValue(newValue, gauge) {
    let option = gauge.getOption();
    let currentValue = option.series[0].data[0].value;
    if (gauge.isCircular !== undefined && gauge.isCircular && Math.abs(newValue - currentValue) > 180) {
        let currentAnimationEasingUpdate = option.series[0].animationEasingUpdate;
        let currentAnimationSetting = option.animation;
        option.series[0].animationEasingUpdate = 'linear';
        let toNorth = 360;
        let fromNorth = 0;
        if (currentValue < 180) {
            toNorth = 0;
            fromNorth = 360;
        }
        option.series[0].data[0].value = toNorth;
        gauge.setOption(option);
        option.animation = false;
        option.series[0].data[0].value = fromNorth;
        gauge.setOption(option);
        option.animation = currentAnimationSetting;
        option.series[0].animationEasingUpdate = currentAnimationEasingUpdate;
        option.series[0].data[0].value = newValue;
        gauge.setOption(option);
    } else {
        option.series[0].data[0].value = newValue;
    }
    gauge.setOption(option);
}

function addValues(chart, jPayload, timestamp) {
    let option = chart.getOption();
    if (option === undefined || option === null) {
        return;
    }
    for (let dataset of option.series) {
        dataset.chartId = chart.chartId;
        let value = convert(chart.weewxData[dataset.weewxColumn], getValue(jPayload, dataset.payloadKey));
        addValueAndUpdateChart(chart, option, dataset, value, timestamp);
    }
}

function addValueAndUpdateChart(chart, option, dataset, value, timestamp) {
    if (!isNaN(value)) {
        let aggregateType = SUM;
        if (chart.weewxData[dataset.weewxColumn].aggregateType !== undefined) {
            aggregateType = chart.weewxData[dataset.weewxColumn].aggregateType;
        }
        if (chart.weewxData[dataset.weewxColumn].aggregateInterval !== undefined) {
            addAggregatedChartValue(dataset, value, timestamp, chart.weewxData[dataset.weewxColumn].aggregateInterval, aggregateType);
            timestamp = Date.now(); // Axis timestamps for aggregated series are not fitting for updating "last updated" in chart
        } else {
            addValue(dataset, value, timestamp);
        }
        chart.setOption(option);

        if (dataset.chartId !== undefined) {
            let chartElem = document.getElementById(dataset.chartId + "_timestamp");
            chartElem.innerHTML = formatDateTime(timestamp);
        }
    }
}

function addValue(dataset, value, timestamp) {
    let type = dataset.weewxColumn;
    let intervalStart = getIntervalStart(timestamp, archiveIntervalSeconds * 1000);
    let data = dataset.data;

    let currentIntervalData = getIntervalData(type, intervalStart);
    if (type === "windSpeed") {
        //some stations update windSpeed more often than gust: if current speed > gust, update gust, but only for current gauge value
        //other values will be updated when regular message arrives
        let windGustGauge = gauges.windGustGauge;
        if (windGustGauge !== undefined && value > windGustGauge.getOption().series[0].data[0].value) {
            setGaugeValue(windGustGauge, value, timestamp);
        }
    }
    currentIntervalData.values.push(value);
    if (data.length > 0 && data[data.length - 1][0] > intervalStart) {
        data.pop();
        value = getIntervalValue(type, currentIntervalData, value);
    }
    data.push([timestamp, value]);
    rotateData(dataset.data);
}

function getIntervalData(type, intervalStart) {
    if (intervalData[type] === undefined || intervalData[type].startTime !== intervalStart) {
        let currentIntervalData = {
            startTime: intervalStart,
            values: []
        };
        intervalData[type] = currentIntervalData;
        return currentIntervalData;
    } else {
        return intervalData[type];
    }
}

function getIntervalValue(type, currentIntervalData, value) {
    if (type === "windGust") {
        return getMaxIntervalValue(currentIntervalData, value);
    }
    if (type === "windDir" && intervalData.windSpeed !== undefined) {
        return calcWindDir(currentIntervalData, intervalData.windSpeed);
    }
    return getAverageIntervalValue(currentIntervalData, value);
}

function getMaxIntervalValue(currentIntervalData, value) {
    let max = value;
    for (let aValue of currentIntervalData.values) {
        if (aValue > max) {
            max = aValue;
        }
    }
    return max;
}

function getAverageIntervalValue(currentIntervalData, value) {
    let sum = value;
    for (let aValue of currentIntervalData.values) {
        value += aValue;
    }
    return value / (currentIntervalData.values.length + 1);
}

function addAggregatedChartValue(dataset, value, timestamp, intervalSeconds, aggregateType) {
    setAggregatedChartEntry(value, timestamp, intervalSeconds, dataset.data, aggregateType);
    rotateData(dataset.data);
}

function setAggregatedChartEntry(value, timestamp, aggregateInterval, data, aggregateType) {
    if (value === null || value === undefined) {
        return;
    }
    let duration = aggregateInterval * 1000;
    let intervalStart = getIntervalStart(timestamp, duration) + duration / 2;
    if (data.length > 0 && data[data.length - 1][0] === intervalStart) {
        let aggregatedValue;
        if (aggregateType === AVG) {
            let valueCount = data[data.length - 1][2];
            aggregatedValue = (Number.parseFloat(data[data.length - 1][1]) * valueCount + value) / (valueCount + 1);
        } else {
            aggregatedValue = Number.parseFloat(data[data.length - 1][1]) + value;
        }
        data[data.length - 1][1] = aggregatedValue;
        data[data.length - 1][2]++;
    } else {
        data.push([intervalStart, value, 1]);
    }
}

function rotateData(data) {
    if (data === undefined || data[0] === undefined || data[0][0] === undefined) {
        return;
    }
    while (data.length > 0 && data[0][0] < Date.now() - maxAgeHoursMS) {
        data.shift();
    }
}

function calculateDewpoint(temp, humidity) {
    humidity = Number.parseFloat(humidity) / 100;
    temp = Number.parseFloat(temp);
    if (temp > 0) {
        return 243.12 * ((17.62 * temp) / (243.12 + temp) + Math.log(humidity)) / ((17.62 * 243.12) / (243.12 + temp) - Math.log(humidity));
    }
    return 272.62 * ((22.46 * temp) / (272.62 + temp) + Math.log(humidity)) / ((22.46 * 272.62) / (272.62 + temp) - Math.log(humidity));
}

function getIntervalStart(timestamp, duration) {
    return Math.floor((+timestamp) / (+duration)) * (+duration)
}

function calcWindDir(windDirIntervaldata, windSpeedIntervaldata) {
    let sumX = 0;
    let sumY = 0;
    for (let i = 0; i < windSpeedIntervaldata.values.length; i++) {
        let windSpeed = windSpeedIntervaldata.values[i];
        if (windSpeed > 0) {
            let windDir = (windDirIntervaldata.values[i]) * Math.PI / 180;
            sumX += Math.cos(windDir) * windSpeed;
            sumY += Math.sin(windDir) * windSpeed;
        }
    }
    let offset = 0;
    if (sumX.toFixed(3) === "0.000" && sumY.toFixed(3) === "0.000") { //no windDir, toFixed because of Number precision
        return NaN;
    } else if (sumX >= 0) {
        if (sumY < 0) {
            offset = 360;
        }
    } else {
        offset = 180;
    }
    return (Math.atan(sumY / sumX) * 180 / Math.PI) + offset;
}

function formatDateTime(timestamp) {
    let date = new Date(timestamp);
    return date.toLocaleDateString(localeWithDash) + ", " + formatTime(timestamp);
}

function formatTime(timestamp) {
    let date = new Date(timestamp);
    return date.toLocaleTimeString(localeWithDash);
}

function checkAsyncReload() {
    log_debug(`async reload due in ${Math.round(archiveIntervalSeconds - (Date.now() - lastAsyncReloadTimestamp) / 1000)} seconds.`);
    if ((Date.now() - lastAsyncReloadTimestamp) / 1000 > archiveIntervalSeconds) {
        fetch("ts.json", {
            cache: "no-store"
        }).then(function (u) {
            return u.json();
        }).then(function (serverData) {
            if (Number.parseInt(serverData.lastGoodStamp) > lastGoodStamp) {
                lastGoodStamp = serverData.lastGoodStamp;
                asyncReloadWeewxData();
                asyncReloadReportData();
                lastAsyncReloadTimestamp = Date.now();
            }
        }).catch(err => {
            throw err
        });
    }
}

function asyncReloadWeewxData() {
    fetch(weewxDataUrl, {
        cache: "no-store"
    }).then(function (u) {
        return u.json();
    }).then(function (serverData) {
        let newerItems = [];
        for (let chartItem of weewxData[CHARTS].live_chart_items) {
            newerItems[chartItem] = [];
            for (let seriesName of Object.keys(weewxData[CHARTS][chartItem])) {
                if (serverData[seriesName] !== undefined && serverData[seriesName].slice(-1)[0] !== undefined) {
                    let seriesData = getSeriesData(chartItem, seriesName);
                    if (seriesData !== undefined) {
                        newerItems[chartItem][seriesName] = setNewerItems(seriesData, serverData[seriesName], weewxData[CHARTS][chartItem], seriesName);
                    }
                }
            }
        }
        weewxData = serverData;
        loadGauges();
        if (typeof loadCharts === 'function') {
            loadCharts();
        }
        let date = new Date(lastGoodStamp * 1000);
        let lastUpdate = document.getElementById("lastUpdate");
        lastUpdate.innerHTML = formatDateTime(date);
        appendNewerItems(newerItems);
    }).catch(err => {
        throw err
    });
}

function asyncReloadReportData() {
    fetch(stationInfoDataUrl, {
        cache: "no-store"
    }).then(function (u) {
        return u.json();
    }).then(function (reportData) {
        for (let aFunction of updateFunctions) {
            aFunction(reportData);
        }
    }).catch(err => {
        throw err
    });
}

function setNewerItems(seriesData, serverSeriesData, configs, seriesName) {
    let config = configs[seriesName];
    let newerItems = [];
    if (config.aggregateInterval === undefined) {
        let newestServerTimestamp = serverSeriesData[serverSeriesData.length - 1][0];
        let aItem = seriesData.pop();
        while (aItem !== undefined && aItem[0] > newestServerTimestamp) {
            newerItems.push(aItem);
            aItem = seriesData.pop();
        }
    } else {
        let aggregatedServerSeriesData = aggregate(serverSeriesData, config.aggregateInterval, config.aggregateType);
        if (aggregatedServerSeriesData.length > 0) {
            let newestServerTimestamp = aggregatedServerSeriesData[aggregatedServerSeriesData.length - 1][0];
            let aItem = seriesData.pop();

            while (aItem !== undefined && aItem[0] >= newestServerTimestamp) {
                if (aItem !== undefined && aItem[0] === newestServerTimestamp) {
                    aggregatedServerSeriesData.pop();
                    aggregatedServerSeriesData.push(aItem);
                }
                if (aItem !== undefined && aItem[0] > newestServerTimestamp) {
                    newerItems.push(aItem);
                }
                aItem = seriesData.pop();
            }
            serverSeriesData = aggregatedServerSeriesData;
        }
    }
    return newerItems;
}

function appendNewerItems(newerItems) {
    for (let chartItem of Object.keys(newerItems)) {
        let chartId = chartItem + CHART;
        let chart = charts[chartId];
        let option = chart.getOption();
        for (let dataset of option.series) {
            dataset.chartId = chartId;
            let newData = newerItems[chartItem][dataset.weewxColumn];
            if (newData.length > 0) {
                for (let data of newData) {
                    let value = data[1];
                    let timestamp = data[0];
                    log_debug(`updating ${dataset.weewxColumn} of ${chartId} value=${value}, timestamp=${timestamp}(${formatDateTime(timestamp)}).`);
                    addValueAndUpdateChart(chart, option, dataset, value, timestamp);
                }
            }
        }
    }
}

function getValue(obj, path) {
    if (path === undefined) {
        return;
    }
    let pathArray = path.split(".");
    let value = obj;
    for (let i = 0; i < pathArray.length; i++) {
        if (value !== undefined && value[pathArray[i]] !== undefined) {
            value = value[pathArray[i]];
        }
    }
    return value;
}

function getSeriesData(chartItem, seriesName) {
    for (let series of charts[chartItem + CHART].getOption().series) {
        if (series.weewxColumn !== undefined && series.weewxColumn === seriesName) {
            return series.data;
        }
    }
    return undefined;
}

function log_debug(message) {
    if (weewxData.config.debug_front_end !== undefined && "true" === weewxData.config.debug_front_end.toLowerCase()) {
        console.log(message);
    }
}

function setInnerHTML(element, value) {
    if (element !== null && element !== undefined && value !== null && value !== undefined) {
        element.innerHTML = value;
    }
}