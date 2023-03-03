<div class="col-md-3">
    <div class="row">
        <div class="col-md-12 text-center">
            <h1 class="currentConditions">$gettext("Current Conditions")</h1>
        </div>
    </div>
    #set $count = 0
    #set $size = len($LiveGauges)
    #for $gauge in $LiveGauges
    #if $count % 2 == 0
    <div class="row">
    #end if
        <div class="gaugecol col-md-6 d-flex justify-content-center">
            <div id="${gauge}Gauge" class="gauge"></div>
        </div>
    #if $count % 2 == 1 or $count == ($size - 1)
    </div>
    #end if
    #set $count = $count + 1
    #end for
    <!-- Station info -->
    <div class="row stationInfo">
        <table class="table table-hover">
            <tbody>
            <tr>
                <td>$gettext("Latitude")</td>
                <td>$station.latitude[0]&deg; $station.latitude[1]' $station.latitude[2]</td>
            </tr>
            <tr>
                <td>$gettext("Longitude")</td>
                <td>$station.longitude[0]&deg; $station.longitude[1]' $station.longitude[2]</td>
            </tr>
            <tr>
                <td>$gettext("Altitude")</td>
                <td>$station.altitude</td>
            </tr>
            <tr>
                <td>$gettext("Sunrise")</td>
                <td>$almanac.sunrise</td>
            </tr>
            <tr>
                <td>$gettext("Sunset")</td>
                <td>$almanac.sunset</td>
            </tr>
            <tr>
                <td>$gettext("Moon Phase")</td>
                <td>$almanac.moon_phase ($almanac.moon_fullness%)</td>
            </tr>
            <tr>
                <td>$gettext("Station Uptime")</td>
                <td>$station.uptime.long_form</td>
            </tr>
            <tr>
                <td>$gettext("Server Uptime")</td>
                <td>$station.os_uptime.long_form</td>
            </tr>
            </tbody>
        </table>
    </div>
</div>
