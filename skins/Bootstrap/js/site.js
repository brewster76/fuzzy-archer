let archiveIntervalMinutes = 5;
let rainAggregateIntervalMinutes = 10;
let mqttConnection = "wss://mqtt.flespi.io:443";
let mqttUsername = "i29R5vj2zIMVKQlXvvGeJYQntKBreHVkxU1sd8jCHVohCz2VTx0qjGDBg4QizBtX";
let mqttPassword;//= "i29R5vj2zIMVKQlXvvGeJYQntKBreHVkxU1sd8jCHVohCz2VTx0qjGDBg4QizBtX";
let locale ="de_AT";
let intervalData = {};

let mqttCredentials;
if(mqttUsername !== undefined) {
    mqttCredentials = {username: mqttUsername};
    if(mqttPassword !== undefined) {
        mqttCredentials["password"] = mqttPassword;
    }
}
let client;
if(mqttCredentials === undefined) {
    client = mqtt.connect(mqttConnection);
} else {
    client = mqtt.connect(mqttConnection, mqttCredentials);
}

moment.locale(locale.split("_")[0]);


let maxAgeHoursMS = 24 * 3600000;

/*let mqttOptions = {
            connectTimeout: 5000,
            hostname: 'broker.hivemq.com',
            port: 8000,
            path: '/mqtt',
            useSSL: true
        };
let client = mqtt.connect(mqttOptions);
client.subscribe('AT/Salzburg/Hallein/Rif/weather/#');*/
client.subscribe('weather/#');

client.on("message", function (topic, payload) {
    console.log(topic);

    let jPayload = JSON.parse(payload);
    let timestamp;
    if (jPayload.dateTime !== undefined) {
      timestamp = parseInt(jPayload.dateTime) * 1000;
    } else {
      timestamp = Date.now();
    }
    if(topic.endsWith('weather/loop')) {
      setGaugeValue(outTempGauge, jPayload.outTemp_C);
      setGaugeValue(barometerGauge, jPayload.altimeter_mbar);
      setGaugeValue(windDirGauge, jPayload.windDir);
      //setGaugeValue(outHumidityGauge, jPayload.outHumidity);
      setGaugeValue(outHumidityGauge, jPayload.extraHumid1);
      setGaugeValue(windSpeedGauge, jPayload.windSpeed_mps * 3.6);
      setGaugeValue(windGustGauge, jPayload.windGust_mps * 3.6);
      
      addValue("outTemp", outTempChart, 0, jPayload.outTemp_C, timestamp);
      addValue("dewPoint", outTempChart, 1, calculateDewpoint(jPayload.extraTemp1_C, jPayload.extraHumid1), timestamp);
      addValue("barometer", barometerChart, 0, jPayload.altimeter_mbar, timestamp);
      //addValue(outHumidityChart, 0, jPayload.outHumidity, timestamp);
      addValue("outHumidity", outHumidityChart, 0, jPayload.extraHumid1, timestamp);
      addValue("windSpeed", windChart, 0, jPayload.windSpeed_mps * 3.6, timestamp);
      addValue("windGust", windChart, 1, jPayload.windGust_mps * 3.6, timestamp);
      addValue("windDir", windDirChart, 0, jPayload.windDir, timestamp);
      //addAggregatedChartValue("rain", rainChart, 0, 0.1, timestamp, rainAggregateIntervalMinutes);
      addAggregatedChartValue("rain", rainChart, 0, jPayload.rain_mm, timestamp, rainAggregateIntervalMinutes);
    }
    else if(topic.endsWith('weather/pvPrivate')) {
      let installedWPeak = 3000;
      addValue("pvOutput", pvOutputChart, 0, jPayload["values"][0].value/installedWPeak, jPayload.timestamp);
    }
    let lastUpdate = document.getElementById("lastUpdate");
    lastUpdate.innerHTML =  moment(timestamp).format("L") + " um " + moment(timestamp).format("LTS");
    
});

function setGaugeValue(gauge, value) {
  if(isNaN(value)) {
    return;
  }
  let option = gauge.getOption();
  option.series[0].data[0].value = value;
  gauge.setOption(option);
}

function addValue(type, chart, datasetIndex, value, timestamp) {
  if(isNaN(value)) {
    return;
  }
  value = Number.parseFloat(value);
  let option = chart.getOption();
  let intervalStart = getIntervalStart(timestamp, archiveIntervalMinutes * 60000);
  let data = option.series[datasetIndex].data;

  let currentIntervalData = getIntervalData(type, intervalStart);
  currentIntervalData.values.push(value);
  if(data.length > 0 && data[data.length - 1][0] > intervalStart) {
    data.pop();
    value = getIntervalValue(type, currentIntervalData, value);
  }
  data.push([timestamp, value]);

  for(let dataset of option.series) {
    rotateData(dataset.data);
  }
  chart.setOption(option);  
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


function addAggregatedChartValue(type, chart, datasetIndex, value, timestamp, intervalMinutes) {
    if(isNaN(value)) {
      value = 0;
    }
    value = Number.parseFloat(value);
    let duration = intervalMinutes * 60000;
    let intervalStart = getIntervalStart(timestamp, duration);
    let option = chart.getOption();
    setAggregatedChartEntry(value, intervalStart + duration/2, option.series[0].data);
    rotateData(option.series[0].data);
    chart.setOption(option);
}

function setAggregatedChartEntry(value, intervalStart, data) {
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