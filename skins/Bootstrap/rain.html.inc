<div class="row $global_station_info_classes">
    <div class="col-2">
        <i class="bi-cloud-rain fs-4" title="$Labels.Generic['rain']"></i>
    </div>
    <div class="col-2">
        <div class="text-nowrap fw-bold stationInfoRainHeader">$gettext('Today')</div>
        <div class="text-nowrap"><span id="stationInfoDayRain">$day.rain.sum</span></div>
        <div class="text-nowrap fw-bold stationInfoRainHeader mt-2">$gettext('24h')</div>
        <div class="text-nowrap"><span id="stationInfo24hrain">$span(hour_delta=24).rain.sum</span></div>
    </div>
    <div class="col-2">
        <div class="text-nowrap fw-bold stationInfoRainHeader">$gettext('This week')</div>
        <div class="text-nowrap"><span id="stationInfoWeekRain">$week.rain.sum</span></div>
        <div class="text-nowrap fw-bold stationInfoRainHeader mt-2">$gettext('72h')</div>
        <div class="text-nowrap"><span id="stationInfo72hrain">$span(hour_delta=72).rain.sum</span></div>
    </div>
    <div class="col-3">
        <div class="text-nowrap fw-bold stationInfoRainHeader">$gettext('This month')</div>
        <div class="text-nowrap"><span id="stationInfoMonthRain">$month.rain.sum</span></div>
        <div class="text-nowrap fw-bold stationInfoRainHeader mt-2">$span(day_delta=30).length.day.format("%d")</div>
        <div class="text-nowrap"><span id="stationInfo30dayRain">$span(day_delta=30).rain.sum</span></div>
    </div>
    <div class="col-3">
        <div class="text-nowrap fw-bold stationInfoRainHeader">$gettext('This year')</div>
        <div class="text-nowrap"><span id="stationInfoMonthRain">$year.rain.sum</span></div>
        <div class="text-nowrap fw-bold stationInfoRainHeader mt-2">$span(day_delta=365).length.day.format("%d")</div>
        <div class="text-nowrap"><span id="stationInfo365DayRain">$span(day_delta=365).rain.sum</span></div>
    </div>
</div>

<script type="text/javascript">
#raw
updateFunctions.push(
    function(reportData) {
        setInnerHTML(document.getElementById("stationInfoDayRain"), reportData.stationInfo.dayRain);
        setInnerHTML(document.getElementById("stationInfoWeekRain"), reportData.stationInfo.weekRain);
        setInnerHTML(document.getElementById("stationInfoMonthRain"), reportData.stationInfo.monthRain);
        setInnerHTML(document.getElementById("stationInfoYearRain"), reportData.stationInfo.yearRain);
        setInnerHTML(document.getElementById("stationInfo24hrain"), reportData.stationInfo["24hRain"]);
        setInnerHTML(document.getElementById("stationInfo72hrain"), reportData.stationInfo["72hRain"]);
        setInnerHTML(document.getElementById("stationInfo30dayRain"), reportData.stationInfo["30dRain"]);
        setInnerHTML(document.getElementById("stationInfo365DayRain"), reportData.stationInfo["365dRain"]);
    }
);
#end raw
</script>