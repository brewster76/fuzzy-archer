<div class="row d-flex align-items-center">
    <div class="col-2">
        <i class="bi-globe2 fs-3" title="$gettext('Latitude'), $gettext('Longitude')"></i>
    </div>
    <div class="col-4">
        <div class="text-nowrap">$station.latitude[0]lstrip('0')&deg; $station.latitude[1]' $station.latitude[2]</div>
        <div class="text-nowrap">$station.longitude[0].lstrip('0')&deg; $station.longitude[1]' $station.longitude[2]</div>
    </div>
    <div class="col-2">
        <i class="bi-arrow-bar-down fs-3" title="$gettext('Altitude')"></i>
    </div>
    <div class="col-4">
        <div class="text-nowrap">$station.altitude</div>
    </div>
</div>