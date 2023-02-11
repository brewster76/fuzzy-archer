<script type="text/javascript">
let readingTypes = [];
</script>
<!-- jQuery (necessary for Bootstrap's JavaScript plugins) -->
<script src="js/jquery-3.6.3.min.js"></script>
<!-- Include all compiled plugins (below), or include individual files as needed -->
<script src="js/bootstrap.bundle.min.js"></script>
<script src="js/mqtt.min.js"></script>
<script src="js/units.js"></script>
<script src="js/site.js"></script>
<script src="js/echarts.min.js"></script>
<script src="js/lang.js"></script>
<script src="js/gauges.js"></script>
<script type="text/javascript"></script>
<script type="text/javascript">
var modalTemplate = `
#include "chartTemplate.html.inc"
`;
</script>
<!-- 'raw' makes Cheetah skip this section so it doesn't get confused by the dollar signs in the js -->
#raw
<script type="text/javascript">
        let href = window.location.href;

        let graphMenu = document.getElementById("graphMenu");
        if(graphMenu != null) {
          let indexLink = document.getElementById("indexHtml");
          indexLink.classList.add("active");
          indexLink.href = "#";
          if(href.endsWith("/")) {
            href += "index.html#";
          }
          let listItems = document.evaluate("a", graphMenu, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
          for(let i = 0; i < listItems.snapshotLength; i++) {
            let item = listItems.snapshotItem(i);
            if(href.includes(item.href)) {
              item.classList.add("btn-primary");
              item.classList.add("primaryLive");
              item.href = "#";
            } else {
              item.classList.add("btn-light");
              item.classList.add("primaryLight");
            }
            if(window.innerWidth < 768) {
              item.href += "graphMenu";
            }
          }
        }

        let listItems = document.evaluate("li/a", document.getElementById("navbarList"), null, XPathResult.UNORDERED_NODE_ITERATOR_TYPE, null);
        let item = listItems.iterateNext();
        while(item != null) {
          if(href.includes(item.href)) {
            item.classList.add("active");
            item.href = "#";
            break;
          }
          item = listItems.iterateNext();
        }

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
</script>
#end raw