<div class="col-md-3 pt-3">
    <div class="row">
        <div class="col-md-12 text-center">
            <h1 class="currentConditions">$gettext("Current Conditions")</h1>
        </div>
    </div>
    #set $live_gauge_items = $to_list($LiveGauges.get('live_gauge_items', ['outTemp', 'barometer', 'windDir', 'outHumidity', 'windSpeed', 'windGust']))
    #set $count = 0
    #set $size = len($live_gauge_items)
    #for $gauge in $live_gauge_items
    #if $count % 2 == 0
    <div class="row">
    #end if
        <div class="gaugecol col-6 d-flex justify-content-center">
            <div id="${gauge}Gauge" class="gauge"></div>
        </div>
    #if $count % 2 == 1 or $count == ($size - 1)
    </div>
    #end if
    #set $count = $count + 1
    #end for
    <!-- Station info -->
    <div class="row stationInfo">
        <table class="table table-hover fs-5">
            <tbody>
            #for $station_info_item in $StationInfo['station_info_items']
            #include $station_info_item + ".html.inc"
            #end for
            </tbody>
        </table>
    </div>
</div>
