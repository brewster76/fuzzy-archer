<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>$gettext("Page Title") $station.location</title>
    <!-- Bootstrap -->
    <link href="css/bootstrap.min.css" rel="stylesheet">
    <link href="css/live.css" rel="stylesheet">
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
