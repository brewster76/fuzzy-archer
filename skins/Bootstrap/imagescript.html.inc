<!DOCTYPE html>
<html lang="$lang">
#include "head.html.inc"
<body>
<!-- Menu navbar -->
#include "nav.html.inc"
<!-- Main container -->
<div class="container-fluid">
    <div class="row">
        <!-- Gauge panel -->
        #include "livegauges.html.inc"
        <!-- Graph panel -->
        <div class="col-md-9 main">
            <p></p>
            #include "graphMenu.html.inc"
            <div class="row" id="modalRow">
                <script type="text/javascript">
                    let readingTypes = [
                    #for $imageName, $value in $ImageGenerator[$global_type + '_images'].items()
                    #if isinstance($value, dict)
                    "${imageName}",
                    #end if
                    #end for
                    ];
                    var modalTemplate = `
                    #include "chartTemplate.html.inc"
                    `;
                    #raw
                    function insertCharts(chartNames) {
                        let modalRow = document.getElementById("modalRow");
                        for(let chartName of chartNames) {
                        let elem = getModalElement(chartName);
                        modalRow.insertAdjacentHTML('beforeend', elem);
                        }
                    }

                    function getModalElement(name) {
                        return modalTemplate.replaceAll("###name###", name);
                    }
                    if(readingTypes !== undefined) {
                        insertCharts(readingTypes);
                    }
                    #end raw
                </script>
            </div>
        </div>
    </div>
    #include "foot.html.inc"
</div>
#include "script.html.inc"
</body>
</html>