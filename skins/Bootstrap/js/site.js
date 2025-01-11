const AVG = "avg";
const SUM = "sum";
const CHART = "Chart";
const CHARTS = "charts";
const DAILY_HIGH_LOW_KEY = "daily_high_low";
const DAILY_MAX = "dailyMax";
const DAILY_MIN = "dailyMin";

let weewxData;
let weewxDataUrl = "weewxData.json";
let stationInfoDataUrl = "reportData.json";
let gauges = {};
let charts = {};
let lastAsyncReloadTimestamp = Date.now();
let lastGoodStamp = lastAsyncReloadTimestamp;
let archiveIntervalSeconds;
let lang;
let eChartsLocale;
let maxAgeHoursMS;
let intervalData = {};
let liveData = [];

fetch(weewxDataUrl, {
    cache: "no-store"
}).then(function (u) {
    return u.json();
}).then(function (serverData) {
    weewxData = serverData;
    archiveIntervalSeconds = Number(weewxData.config.archive_interval);
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
                checkAsyncReload();
                liveData.push([timestamp, jPayload]);
                updateGaugesAndCharts(timestamp, jPayload);

                let lastUpdate = document.getElementById("lastUpdate");
                lastUpdate.innerHTML = formatDateTime(new Date(timestamp));
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
    throw err;
});

setInterval(checkAsyncReload, 60000);

function updateGaugesAndCharts(timestamp, jPayload) {
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
}

function clearStaleLiveData() {
    let index = 0;
    for (let entry of liveData) {
        if (entry[0] > lastGoodStamp) {
            break;
        }
        index++;
    }
    liveData = liveData.slice(index);
}

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
    option.series[0].pointer.show = true;
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
            addAggregatedChartValue(dataset, value, timestamp, chart.weewxData[dataset.weewxColumn].aggregateInterval, aggregateType, chart.weewxData[dataset.weewxColumn].decimals);
            timestamp = Date.now(); // Axis timestamps for aggregated series are not fitting for updating "last updated" in chart
        } else {
            addValue(dataset, value, timestamp);
        }
        if (dataset.markPoint !== undefined) {
            updateMinMax(dataset, value, timestamp);
        }
        chart.setOption(option);

        if (dataset.chartId !== undefined) {
            let chartElem = document.getElementById(dataset.chartId + "_timestamp");
            chartElem.innerHTML = formatDateTime(timestamp);
        }
    }
}

function updateMinMax(dataset, value, timestamp) {
    let markpointData = dataset.markPoint.data;
    if (markpointData !== undefined && markpointData !== null && markpointData.length > 0) {
        let lastMarkPoint = dataset.markPoint.data[dataset.markPoint.data.length - 1];
        checkAndUpdateMarkpoint(dataset, lastMarkPoint, value, timestamp);
        if (markpointData.length > 1) {
            let nextMarkPoint = dataset.markPoint.data[dataset.markPoint.data.length - 2];
            if (nextMarkPoint.name !== lastMarkPoint.name) {
                checkAndUpdateMarkpoint(dataset, nextMarkPoint, value, timestamp);
            }
        }
    }
}

function checkAndUpdateMarkpoint(dataset, markPoint, value, timestamp) {
    if (markPoint.name === DAILY_MAX && value > markPoint.coord[1]) {
        markPoint.coord[0] = timestamp;
        markPoint.coord[1] = value;
        markPoint.label.formatter = format(value, dataset.decimals);
    }
    if (markPoint.name === DAILY_MIN && value < markPoint.coord[1]) {
        markPoint.coord[0] = timestamp;
        markPoint.coord[1] = value;
        markPoint.label.formatter = format(value, dataset.decimals);
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
    setAggregatedChartEntry(value, timestamp, intervalSeconds, dataset.data, aggregateType, dataset.decimals);
    rotateData(dataset.data);
}

function setAggregatedChartEntry(value, timestamp, aggregateInterval, data, aggregateType, decimals) {
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
        data[data.length - 1][1] = round(aggregatedValue, decimals + 1);
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
    return date.toLocaleDateString(jsLocale) + ", " + formatTime(timestamp);
}

function formatTime(timestamp) {
    let date = new Date(timestamp);
    return date.toLocaleTimeString(jsLocale);
}

function checkAsyncReload(retryCount) {
    log_debug(`async reload due in ${Math.round(archiveIntervalSeconds - (Date.now() - lastAsyncReloadTimestamp) / 1000)} seconds.`);
    if ((Date.now() - lastAsyncReloadTimestamp) > archiveIntervalSeconds * 1000) {
        fetch("ts.json", {
            cache: "no-store"
        }).then(function (u) {
            return u.json();
        }).then(function (serverData) {
            let newLastGoodStamp = Number.parseInt(serverData.lastGoodStamp) * 1000;
            if (newLastGoodStamp > lastGoodStamp) {
                lastGoodStamp = newLastGoodStamp;
                asyncReloadWeewxData();
                asyncReloadReportData();
                lastAsyncReloadTimestamp = Date.now();
            }
        }).catch(err => {
            retryCount = retryCount === undefined ? 0 : ++retryCount;
            if (retryCount < 10) {
                console.log('Retrying fetch #%d, %d', retryCount, Date.now());
                setTimeout(checkAsyncReload, 1000, retryCount);
                return;
            } else {
                throw err;
            }
        });
    }
}

function asyncReloadWeewxData() {
    fetch(weewxDataUrl, {
        cache: "no-store"
    }).then(function (u) {
        return u.json();
    }).then(function (serverData) {
        weewxData = serverData;
        loadGauges();
        if (typeof loadCharts === 'function') {
            loadCharts();
        } else {
            setTimeout(loadCharts, 1000);
        }
        appendLiveData();
        let date = new Date(lastGoodStamp);
        let lastUpdate = document.getElementById("lastUpdate");
        lastUpdate.innerHTML = formatDateTime(date);
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
    });
}

function appendLiveData() {
    clearStaleLiveData();
    for (let dataItem of liveData) {
        updateGaugesAndCharts(dataItem[0], dataItem[1]);
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
    if (charts[chartItem + CHART] !== undefined) {
        for (let series of charts[chartItem + CHART].getOption().series) {
            if (series.weewxColumn !== undefined && series.weewxColumn === seriesName) {
                return series.data;
            }
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

function aggregate(data, aggregateInterval, aggregateType, decimals) {
    if (aggregateInterval === undefined || aggregateType === undefined) {
        return data;
    }
    let aggregatedData = [];
    if (data !== null && data !== undefined) {
        //timestamp needs to be shifted one archive_interval to show the readings in the correct time window
        let shiftInterval = Number(weewxData.config.archive_interval) * 1000;
        for (let entry of data) {
            if (entry[1] !== undefined) {
                setAggregatedChartEntry(entry[1], entry[0] - shiftInterval, aggregateInterval, aggregatedData, aggregateType, decimals);
            }
        }
    }
    return aggregatedData;
}
