let observationGroups = {
    altimeter: "group_pressure",
    altimeterRate: "group_pressurerate",
    altitude: "group_altitude",
    appTemp: "group_temperature",
    appTemp1: "group_temperature",
    barometer: "group_pressure",
    barometerRate: "group_pressurerate",
    cloudbase: "group_altitude",
    co: "group_fraction",
    co2: "group_fraction",
    consBatteryVoltage: "group_volt",
    cooldeg: "group_degree_day",
    dateTime: "group_time",
    dayRain: "group_rain",
    dewpoint: "group_temperature",
    dewpoint1: "group_temperature",
    ET: "group_rain",
    extraHumid1: "group_percent",
    extraHumid2: "group_percent",
    extraHumid3: "group_percent",
    extraHumid4: "group_percent",
    extraHumid5: "group_percent",
    extraHumid6: "group_percent",
    extraHumid7: "group_percent",
    extraHumid8: "group_percent",
    extraTemp1: "group_temperature",
    extraTemp2: "group_temperature",
    extraTemp3: "group_temperature",
    extraTemp4: "group_temperature",
    extraTemp5: "group_temperature",
    extraTemp6: "group_temperature",
    extraTemp7: "group_temperature",
    extraTemp8: "group_temperature",
    growdeg: "group_degree_day",
    gustdir: "group_direction",
    hail: "group_rain",
    hailRate: "group_rainrate",
    heatdeg: "group_degree_day",
    heatindex: "group_temperature",
    heatindex1: "group_temperature",
    heatingTemp: "group_temperature",
    heatingVoltage: "group_volt",
    hourRain: "group_rain",
    humidex: "group_temperature",
    humidex1: "group_temperature",
    illuminance: "group_illuminance",
    inDewpoint: "group_temperature",
    inHumidity: "group_percent",
    inTemp: "group_temperature",
    interval: "group_interval",
    leafTemp1: "group_temperature",
    leafTemp2: "group_temperature",
    leafTemp3: "group_temperature",
    leafTemp4: "group_temperature",
    leafWet1: "group_count",
    leafWet2: "group_count",
    lightning_distance: "group_distance",
    lightning_disturber_count: "group_count",
    lightning_noise_count: "group_count",
    lightning_strike_count: "group_count",
    maxSolarRad: "group_radiation",
    monthRain: "group_rain",
    nh3: "group_fraction",
    no2: "group_concentration",
    noise: "group_db",
    o3: "group_fraction",
    outHumidity: "group_percent",
    outTemp: "group_temperature",
    pb: "group_fraction",
    pm1_0: "group_concentration",
    pm2_5: "group_concentration",
    pm10_0: "group_concentration",
    pressure: "group_pressure",
    pressureRate: "group_pressurerate",
    radiation: "group_radiation",
    rain: "group_rain",
    rain24: "group_rain",
    rainRate: "group_rainrate",
    referenceVoltage: "group_volt",
    rms: "group_speed2",
    rxCheckPercent: "group_percent",
    snow: "group_rain",
    snowDepth: "group_rain",
    snowMoisture: "group_percent",
    snowRate: "group_rainrate",
    so2: "group_fraction",
    soilMoist1: "group_moisture",
    soilMoist2: "group_moisture",
    soilMoist3: "group_moisture",
    soilMoist4: "group_moisture",
    soilTemp1: "group_temperature",
    soilTemp2: "group_temperature",
    soilTemp3: "group_temperature",
    soilTemp4: "group_temperature",
    stormRain: "group_rain",
    stormStart: "group_time",
    supplyVoltage: "group_volt",
    THSW: "group_temperature",
    totalRain: "group_rain",
    UV: "group_uv",
    vecavg: "group_speed2",
    vecdir: "group_direction",
    wind: "group_speed",
    windchill: "group_temperature",
    windDir: "group_direction",
    windGust: "group_speed",
    windGustDir: "group_direction",
    windgustvec: "group_speed",
    windrun: "group_distance",
    windSpeed: "group_speed",
    windSpeed10: "group_speed",
    windvec: "group_speed",
    yearRain: "group_rain",
}

function convert(itemConfig, value) {
    if(isNaN(value)) {
      return;
    }
    value = Number.parseFloat(value);

    if(itemConfig.convertFunction !== undefined && itemConfig.convertFunction !== null && itemConfig.convertFunction !== "") {
        let convertFunction = new Function("return " + itemConfig.convertFunction)();
        return convertFunction(value);
    }

    let sourceUnit = itemConfig.source_unit;
    if(sourceUnit === undefined && sourceUnit !== null && sourceUnit !== "") {
        return value;
    }

    let group = observationGroups[itemConfig.observationType];
    let targetUnit = weewxData.units.Groups[group];
    if(sourceUnit === targetUnit) {
      return value;
    }
    let functionName = sourceUnit + "_To_" + targetUnit;
    if(window[functionName] !== undefined) {
      return window[functionName](value);
    }
    //console.log("Couldn't find conversion function: '" + functionName + "', returning value without conversion");
    return value;
}

function meter_per_second_To_km_per_hour(value) {
    return value * 3.6;
}
