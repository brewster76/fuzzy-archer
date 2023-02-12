<script type="text/javascript">
var modalTemplate = `
#include "chartTemplate.html.inc"
`;
<!-- 'raw' makes Cheetah skip this section so it doesn't get confused by the dollar signs in the js -->
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