<div class="row $global_station_info_classes">
    <div class="col-2">
        <i class="bi-sunrise fs-4" title="$gettext('Sunrise')"></i>
    </div>
    <div class="col-4">
        <div class="text-nowrap"><span id="stationInfoSunRise">$almanac.sunrise</span></div>
    </div>
    <div class="col-2">
        <i class="bi-sunset fs-4" title="$gettext('Sunset')"></i>
    </div>
    <div class="col-4">
        <div class="text-nowrap"><span id="stationInfoSunSet">$almanac.sunset</span></div>
    </div>
</div>

<script type="text/javascript">
#raw
updateFunctions.push(
    function(reportData) {
        setInnerHTML(document.getElementById("stationInfoSunRise"), reportData.stationInfo.sunrise);
        setInnerHTML(document.getElementById("stationInfoSunSet"), reportData.stationInfo.sunset);
    }
);
#end raw
</script>