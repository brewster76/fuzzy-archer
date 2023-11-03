<!DOCTYPE html>
<html lang="$lang">
#include "head.html.inc"
<body>
<!-- Menu navbar -->
#include "nav.html.inc"
<!-- Main container -->
<div class="container-fluid pt-3">
    <div class="row pt-3">
        <!-- Gauge panel -->
        #include "livegauges.html.inc"
        <!-- Graph panel -->
        <div class="col-md-9 main pt-md-3">
            <p></p>
            #include "graphMenu.html.inc"
            <div class="row" id="modalRow">
                    #for $imageName in $image_items
                    #set $imageItem = $ImageGenerator[$global_type + '_images'][$imageName]
                    #if isinstance($imageItem, dict)
                    <div class="chart">
                        <div class="modal fade" id="large-${imageName}Modal" tabindex="-1" aria-hidden="true">
                            <div class="modal-dialog" style="max-width: 900px">
                                <div class="modal-content">
                                    <div class="modal-header">
                                        <button type="button" class="btn-close" data-bs-dismiss="modal"
                                                aria-label="Close"></button>
                                    </div>
                                    <div class="modal-body">
                                        <img src="large-${imageName}.png" alt="" class="mw-100">
                                    </div>
                                    <div class="modal-footer"></div>
                                </div>
                            </div>
                        </div>
                        <img src="${imageName}.png" alt="" title="$gettext('Click to enlarge')" class="mw-100"
                             data-bs-toggle="modal" data-bs-target="#large-${imageName}Modal" style="cursor: pointer;">
                    </div>
                    #end if
                    #end for
            </div>
        </div>
    </div>
    #include "foot.html.inc"
</div>
#include "script.html.inc"
</body>
</html>
