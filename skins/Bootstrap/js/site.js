moment.locale('de');
//let client = mqtt.connect("ws://10.0.1.90:9001");
let client = mqtt.connect("wss://mqtt.flespi.io:443", {
  username: "i29R5vj2zIMVKQlXvvGeJYQntKBreHVkxU1sd8jCHVohCz2VTx0qjGDBg4QizBtX"
});

let maxAgeHoursMS = 6 * 3600000;

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
      
      addValue(outTempChart, 0, jPayload.outTemp_C, timestamp, 1);
      console.log(JSON.stringify(outTempChart._model.option.series[0].data));
      addValue(outTempChart, 1, jPayload.dewpoint_C, timestamp, 1);
      addValue(barometerChart, 0, jPayload.altimeter_mbar, timestamp, 1);
      //addValue(outHumidityChart, 0, jPayload.outHumidity, timestamp, 0);
      addValue(outHumidityChart, 0, jPayload.extraHumid1, timestamp, 0);
      addValue(windChart, 0, jPayload.windSpeed_mps * 3.6, timestamp, 0);
      addValue(windChart, 1, jPayload.windGust_mps * 3.6, timestamp, 0);
      addValue(windDirChart, 0, jPayload.windDir, timestamp, 1);
      addRainChartValue(jPayload.rain_mm, timestamp, 10);
    }
    else if(topic.endsWith('weather/pvPrivate')) {
      let installedWPeak = 3000;
      addValue(pvOutputChart, 0, jPayload["values"][0].value/installedWPeak, jPayload.timestamp, 3);
    }
    let lastUpdate = document.getElementById("lastUpdate");
    lastUpdate.innerHTML =  moment(timestamp).format("L") + " um " + moment(timestamp).format("LTS");
    
    /*chart.data.labels.push(timestamp);
    for (let sensorId of Object.keys(sensors)) {
        if (sensorId !== sensorIdFromTopic && jPayload[sensorId] === undefined) {
            continue;
        }
        let sensor = sensors[sensorId];
        for (let typeId of sensor.types) {
            let rawValue;
            if (client.type === "WEEWX") {
                rawValue = getValueFromWeeWXPayload(sensorIdFromTopic, sensorId, jPayload);
            } else {
                rawValue = getValueFromPayload(typeId, jPayload);
            }
            if (isNaN(rawValue)) {
                rawValue = undefined;
            }
            let dataset = findDatasetById(chart.data.datasets, getDatasetId(sensorId, typeId));
            if (dataset === undefined) {
                continue;
            }
            let value = calibrate(sensorId, typeId, rawValue);
            if (rotate) {
                dataset.data.shift();
            }
            dataset.data.push(value);
        }
    }*/
    
});

function setGaugeValue(gauge, value) {
  if(isNaN(value)) {
    return;
  }
  let option = gauge.getOption();
  option.series[0].data[0].value = value;
  gauge.setOption(option);
}

function addValue(chart, datasetIndex, value, timestamp, toFixed) {
  if(isNaN(value)) {
    return;
  }
  if(toFixed !== undefined) {
    value = Number.parseFloat(value).toFixed(toFixed);
  }
  let option = chart.getOption();
  option.series[datasetIndex].data.push([timestamp, value]);
  for(let dataset of option.series) {
    removeData(dataset.data);
  }
  chart.setOption(option);  
}

function addRainChartValue(rainValue, timestamp, intervalMinutes) {
    if(isNaN(rainValue)) {
      rainValue = 0;
    }
    rainValue = Number.parseFloat(rainValue);
    let duration = intervalMinutes * 60000;
    let intervalStart = Math.floor((+timestamp) / (+duration)) * (+duration);
    let option = rainChart.getOption();
    setRainChartEntry(rainValue, intervalStart, option.series[0].data);
    removeData(option.series[0].data);
    rainChart.setOption(option);
}

function setRainChartEntry(rainValue, intervalStart, data) {
  if(data.length > 0 && data[data.length-1][0] === intervalStart) {
    let intervalSum = Number.parseFloat(data[data.length-1][1]) + rainValue;
    data[data.length-1][1] = intervalSum.toFixed(2);
  } else {
    data.push([intervalStart, rainValue.toFixed(1)]);
  }
}

function removeData(data){
    if(data === undefined || data[0] === undefined || data[0][0] === undefined) {
      return;
    }
    while(data[0][0] < Date.now() - maxAgeHoursMS) {
      data.shift();
    }
}