<div class="row $global_station_info_classes">
    <div class="col-2">
        <i class="bi-moon fs-4" title="$gettext('Moon Phase')"></i>
    </div>
    <div class="col-4">
        <div><span id="stationInfoMoonPhase">$almanac.moon_phase</span> (<span id="stationInfoMoonFullness">$almanac.moon_fullness</span>%)</div>
    </div>
    <div class="col-6">
        <div class="text-nowrap"><i class="bi-arrow-up-short fs-6" title="$gettext('Moonrise')"></i><span id="stationInfoMoonRise">$almanac.moon.rise</span></div>
        <div class="text-nowrap"><i class="bi-arrow-down-short fs-6" title="$gettext('Moonset')"></i><span id="stationInfoMoonSet">$almanac.moon.set</span></div>
    </div>
</div>

<script type="text/javascript">
#raw
updateFunctions.push(
    function(reportData) {
        setInnerHTML(document.getElementById("stationInfoMoonPhase"), reportData.stationInfo.moonPhase);
        setInnerHTML(document.getElementById("stationInfoMoonFullness"), reportData.stationInfo.moonFullness);
        setInnerHTML(document.getElementById("stationInfoMoonRise"), reportData.stationInfo.moonrise);
        setInnerHTML(document.getElementById("stationInfoMoonSet"), reportData.stationInfo.moonset);
    }
);
#end raw
</script>