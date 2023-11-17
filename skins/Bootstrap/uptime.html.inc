<div class="row $global_station_info_classes">
    <div class="col-2">
        <i class="bi-clock-history fs-3" title="$gettext('Station Uptime')"></i>
    </div>
    <div class="col-10">
        <div class="text-nowrap"><span id="stationInfoStationUptime">$station.uptime.long_form</span></div>
    </div>
</div>
<div class="row $global_station_info_classes">
    <div class="col-2">
        <i class="bi-clock-history fs-3" title="$gettext('Server Uptime')"></i>
    </div>
    <div class="col-10">
        <div class="text-nowrap"><span id="stationInfoServerUptime">$station.os_uptime.long_form</span></div>
    </div>
</div>

<script type="text/javascript">
#raw
updateFunctions.push(
    function(reportData) {
        setInnerHTML(document.getElementById("stationInfoStationUptime"), reportData.stationInfo.stationUptime);
        setInnerHTML(document.getElementById("stationInfoServerUptime"), reportData.stationInfo.stationOSUptime);
    }
);
#end raw
</script>