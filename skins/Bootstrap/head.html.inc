<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>$gettext("Page Title") $station.location</title>
    <!-- Bootstrap -->
    <link href="css/bootstrap.min.css" rel="stylesheet">
    <link href="css/bootstrap-icons.min.css" rel="stylesheet">
    <link href="css/live.css" rel="stylesheet">
    #set $extra_css = $to_list($Extras.get('extra_css', []))
    #for $css in $extra_css
    <link href="css/$css" rel="stylesheet">
    #end for
    #set $extra_css = $to_list($Extras.get('extra_js', []))
    #for $js in $extra_css
    <script src="js/$js"></script>
    #end for
    <script type="text/javascript">
    let locale = "$locale";
    function decodeHtml(html) {
        var txt = document.createElement("textarea");
        txt.innerHTML = html;
        return txt.value;
    }
    function setToolboxVisibility(chartDiv, show) {
        try {
            let chart = charts[chartDiv.id];
            chart.setOption({
                toolbox: { show: show }
            });
        } catch(e) {
            //not ready
        }
    }
    </script>
</head>
