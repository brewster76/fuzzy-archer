let archiveIntervalSeconds = weewxData.config.archive_interval;
let locale = weewxData.config.locale;
moment.locale(locale.split("_")[0]);
let maxAgeHoursMS = weewxData.config.timespan * 3600000;
let intervalData = {};

let clients = [];
if(weewxData !== undefined && weewxData.config !== undefined && weewxData.config.MQTT !== undefined &&  weewxData.config.MQTT.connections !== undefined) {
    for(let connectionId of Object.keys(weewxData.config.MQTT.connections)) {
        let connection = weewxData.config.MQTT.connections[connectionId];
        let mqttConnection = connection.broker_connection;
        let mqttUsername = connection.mqtt_username;
        let mqttPassword = connection.mqtt_password;
        let intervalData = {};

        let mqttCredentials;
        if(mqttUsername !== undefined) {
            mqttCredentials = {username: mqttUsername};
            if(mqttPassword !== undefined) {
                mqttCredentials["password"] = mqttPassword;
            }
        }
        if(mqttCredentials === undefined) {
            client = mqtt.connect(mqttConnection);
        } else {
            client = mqtt.connect(mqttConnection, mqttCredentials);
        }
        client.topics = connection.topics;
        clients.push(client);

        for(let topic of Object.keys(connection.topics)) {
            client.subscribe(topic);
        }

        client.on("message", function (topic, payload) {
            console.log(topic);
            let jPayload = {};
            let topicConfig = this.topics[topic];
            if(topicConfig.type.toUpperCase() === "JSON") {
                jPayload = JSON.parse(payload);
            } else if (topicConfig.type.toLowerCase() === "plain" && topicConfig.payload_key !== undefined) {
                jPayload[topicConfig.payload_key] = parseFloat(payload);
            } else {
                return;
            }

            let timestamp;
            if (jPayload.dateTime !== undefined) {
              timestamp = parseInt(jPayload.dateTime) * 1000;
            } else {
              timestamp = Date.now();
            }
              for(let gaugeId of Object.keys(gauges)) {
                  let gauge = gauges[gaugeId];
                  let value = convert(gauge.weewxData, jPayload[gauge.weewxData.payload_key]);
                  if(!isNaN(value)) {
                      setGaugeValue(gauge, value);
                  }
              }

              for(let chartId of Object.keys(charts)) {
                  let chart = charts[chartId];
                  if(chart.weewxData.aggregate_interval_minutes !== undefined) {
                      addAggregatedChartValues(chart, jPayload, timestamp, chart.weewxData.aggregate_interval_minutes);
                  } else {
                      addValues(chart, jPayload, timestamp);
                  }
              }
            let lastUpdate = document.getElementById("lastUpdate");
            lastUpdate.innerHTML =  moment(timestamp).format("L") + " um " + moment(timestamp).format("LTS");

        });
    }
}
function setGaugeValue(gauge, value) {
  let option = gauge.getOption();
  option.series[0].data[0].value = value;
  gauge.setOption(option);
}

function addAggregatedChartValues(chart, jPayload, timestamp, aggregateIntervalMinutes) {
    let option = chart.getOption();
    for(let dataset of option.series) {
        let value = convert(chart.weewxData[dataset.weewxColumn], jPayload[dataset.payloadKey]);
        if(!isNaN(value)) {
            addAggregatedChartValue(dataset, value, timestamp, aggregateIntervalMinutes);
            chart.setOption(option);
        }
    }
}

function addValues(chart, jPayload, timestamp) {
    let option = chart.getOption();
    for(let dataset of option.series) {
        let value = convert(chart.weewxData[dataset.weewxColumn], jPayload[dataset.payloadKey]);
        if(!isNaN(value)) {
            addValue(dataset, value, timestamp);
            chart.setOption(option);
        }
    }
}

function addValue(dataset, value, timestamp) {
  let type = dataset.weewxColumn;
  let intervalStart = getIntervalStart(timestamp, archiveIntervalSeconds * 1000);
  let data = dataset.data;

  let currentIntervalData = getIntervalData(type, intervalStart);
  currentIntervalData.values.push(value);
  if(data.length > 0 && data[data.length - 1][0] > intervalStart) {
    data.pop();
    value = getIntervalValue(type, currentIntervalData, value);
  }
  data.push([timestamp, value]);
  rotateData(dataset.data);
}

function getIntervalData(type,  intervalStart) {
    if(intervalData[type] === undefined || intervalData[type].startTime !== intervalStart) {
        let currentIntervalData = {startTime: intervalStart, values: []};
        intervalData[type] = currentIntervalData;
        return currentIntervalData;
    } else {
        return currentIntervalData = intervalData[type];
    }
}

function getIntervalValue(type, currentIntervalData, value) {
    if(type === "windGust") {
        return getMaxIntervalValue(currentIntervalData, value);
    }
    if(type === "windDir") {
        return calcWindDir(currentIntervalData, intervalData.windSpeed);
    }
    return getAverageIntervalValue(currentIntervalData, value);
}

function getMaxIntervalValue(currentIntervalData, value) {
    let max = value;
    for(let aValue of currentIntervalData.values) {
        if(aValue > max) {
            max = aValue;
        }
    }
    return max;
}

function getAverageIntervalValue(currentIntervalData, value) {
    let sum = value;
    for(let aValue of currentIntervalData.values) {
        value += aValue;
    }
    return value / (currentIntervalData.values.length + 1);
}

function addAggregatedChartValue(dataset, value, timestamp, intervalMinutes) {
    setAggregatedChartEntry(value, timestamp, intervalMinutes, dataset.data);
    rotateData(dataset.data);
}

function setAggregatedChartEntry(value, timestamp, intervalMinutes, data) {
  let duration = intervalMinutes * 60000;
  let intervalStart = getIntervalStart(timestamp, duration) + duration/2;
  if(data.length > 0 && data[data.length-1][0] === intervalStart) {
    let intervalSum = Number.parseFloat(data[data.length-1][1]) + value;
    data[data.length-1][1] = intervalSum;
  } else {
    data.push([intervalStart, value]);
  }
}

function rotateData(data){
    if(data === undefined || data[0] === undefined || data[0][0] === undefined) {
      return;
    }
    while(data.length > 0 && data[0][0] < Date.now() - maxAgeHoursMS) {
      data.shift();
    }
}

function calculateDewpoints(tempData, humidityData) {
    let dewpointData = [];
    let index = 0;
    for(let temp of tempData) {
        dewpointData.push([temp[0], calculateDewpoint(temp[1], humidityData[index++][1])]);
    }
    return dewpointData;
}

function calculateDewpoint(temp, humidity) {
    humidity =  Number.parseFloat(humidity) / 100;
    temp =  Number.parseFloat(temp);
    if(temp > 0) {
      return 243.12*((17.62*temp)/(243.12+temp)+Math.log(humidity))/((17.62*243.12)/(243.12+temp)-Math.log(humidity));
    }
    return 272.62*((22.46*temp)/(272.62+temp)+Math.log(humidity))/((22.46*272.62)/(272.62+temp)-Math.log(humidity));
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