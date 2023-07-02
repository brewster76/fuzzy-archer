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

    let sourceUnit = weewxData.source_unit_system[itemConfig.obs_group];
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

function round(value, precision) {
    var multiplier = Math.pow(10, precision || 0);
    return Math.round(value * multiplier) / multiplier;
}

//group_altitude
function meter_To_foot(value) {
    return value * 3.280839895013123;
}
function foot_To_meter(value) {
    return value * 0.3048;
}
//group_degree_day
function degree_F_day_To_degree_C_day(value) {
    return degree_F_To_degree_C(value);
}
function degree_C_day_To_degree_F_day(value) {
    return degree_C_To_degree_F(value);
}
//group_distance
function mile_To_km(value) {
    return value * 1.609344;
}
function km_To_mile(value) {
    return value * 0.621371192237334;
}
//group_pressure
function inHg_To_mmHg(value) {
    return inch_To_mm(value);
}
function inHg_To_mbar(value) {
    return value * 33.8638815789;
}
function inHg_To_hPa(value) {
    return inHg_To_mbar(value);
}
function inHg_To_kPa(value) {
    return hPa_To_kPa(inHg_To_hPa(value));
}

function mmHg_To_inHg(value) {
    return mm_To_inch(value);
}
function mmHg_To_mbar(value) {
    return value * 1.33322368421;
}
function mmHg_To_hPa(value) {
    return mmHg_To_mbar(value);
}
function mmHg_To_kPa(value) {
    return hPa_To_kPa(mmHg_To_hPa(value));
}

function mbar_To_inHg(value) {
    return value * 0.029529987508079485;
}
function mbar_To_mmHg(value) {
    return value * 0.7500616827044659;
}
function mbar_To_hPa(value) {
    return value;
}
function mbar_To_kPa(value) {
    return hPa_To_kPa(hPa_To_mbar(value));
}

function hPa_To_inHg(value) {
    return mbar_To_inHg(value);
}
function hPa_To_mmHg(value) {
    return mbar_To_mmHg(value);
}
function hPa_To_mbar(value) {
    return value;
}
function hPa_To_kPa(value) {
    return value * 0.1;
}

function kPa_To_inHg(value) {
    return value * 0.29529987508079486;
}
function kPa_To_mmHg(value) {
    return value * 7.5006168270446585;
}
function kPa_To_mbar(value) {
    return value * 10;
}
function kPa_To_hPa(value) {
    return hPa_To_kPa(value);
}
//group_rain
function inch_To_mm(value) {
    return value * 25.3999999999745;
}
function inch_To_cm(value) {
    return value * 2.53999999999745;
}
function mm_To_cm(value) {
    return value * 0.1;
}
function mm_To_inch(value) {
    return mm_To_cm(cm_To_inch(value));
}
function cm_To_mm(value) {
    return value * 10;
}
function cm_To_inch(value) {
    return value * 0.3937007874015748;
}
//group_rainrate
function inch_per_hour_To_mm_per_hour(value) {
    return inch_To_mm(value);
}
function inch_per_hour_To_cm_per_hour(value) {
    return inch_To_cm(value);
}
function mm_per_hour_To_cm_per_hour(value) {
    return mm_To_cm(value);
}
function mm_per_hour_To_inch_per_hour(value) {
    return mm_To_inch(value);
}
function cm_per_hour_To_mm_per_hour(value) {
    return cm_To_mm(value);
}
function cm_per_hour_To_inch_per_hour(value) {
    return cm_To_inch(value);
}
//group_speed
function meter_per_second_To_km_per_hour(value) {
    return value * 3.6;
}
function meter_per_second_To_mile_per_hour(value) {
    return value * 2.2369362920544025;
}
function meter_per_second_To_knot(value) {
    return value * 1.94384;
}

function km_per_hour_To_meter_per_second(value) {
    return value / 3.6;
}
function km_per_hour_To_mile_per_hour(value) {
    return km_To_mile(value);
}
function km_per_hour_To_knot(value) {
    return value * 0.539957;
}

function mile_per_hour_To_meter_per_second(value) {
    return value * 0.44704;
}
function mile_per_hour_To_km_per_hour(value) {
    return mile_To_km(value);
}
function mile_per_hour_To_knot(value) {
    return value * 0.868976;
}

function knot_To_meter_per_second(value) {
    return value * 0.514444;
}
function knot_To_km_per_hour(value) {
    return value * 1.852;
}
function knot_To_mile_per_hour(value) {
    return value * 1.15078;
}
//group_speed2
function meter_per_second2_To_km_per_hour2(value) {
    return meter_per_second_To_km_per_hour(value);
}
function meter_per_second2_To_mile_per_hour2(value) {
    return meter_per_second_To_mile_per_hour(value);
}
function meter_per_second2_To_knot2(value) {
    return meter_per_second_To_knot(value);
}

function km_per_hour2_To_meter_per_second2(value) {
    return km_per_hour_To_meter_per_second(value);
}
function km_per_hour2_To_mile_per_hour2(value) {
    return km_per_hour_To_mile_per_hour(value);
}
function km_per_hour2_To_knot2(value) {
    return km_per_hour_To_knot(value);
}

function mile_per_hour2_To_meter_per_second2(value) {
    return mile_per_hour_To_meter_per_second(value);
}
function mile_per_hour2_To_km_per_hour2(value) {
    return mile_per_hour_To_km_per_hour(value);
}
function mile_per_hour2_To_knot2(value) {
    return mile_per_hour_To_knot(value);
}

function knot2_To_meter_per_second2(value) {
    return knot_To_meter_per_second(value);
}
function knot2_To_km_per_hour2(value) {
    return knot_To_km_per_hour(value);
}
function knot2_To_mile_per_hour2(value) {
    return knot_To_mile_per_hour(value);
}
//group_temperature
function degree_F_To_degree_C(value) {
    return (value - 32) * 5 / 9;
}
function degree_C_To_degree_F(value) {
    return (value * 9 / 5) + 32;
}

function getUnitString(shownValue, unit) {
    if(unit === undefined) {
        return "";
    }
    if(Array.isArray(unit) && unit.length > 1 && Number(shownValue) !== 1) {
        return unit[1];
    }
    return unit;
}