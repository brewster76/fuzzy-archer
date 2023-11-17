#set $graphMenuItems = [{'href': 'index.html', 'text': 'Live'}, {'href': 'day.html', 'text': '24 Hours'}, {'href': 'week.html', 'text': 'Week'}, {'href': 'month.html', 'text': 'Month'}, {'href': 'year.html', 'text': 'Year'}]
<section id="menu"></section>
<p id="graphMenu" class="my-1 mt-md-0">
    #for $graphMenuItem in $graphMenuItems
    #set $classlist = ' btn-light primaryLight'
    #set $href = $graphMenuItem['href']
    #if $graphMenuItem['href'] in $filename
    #set $classlist = ' btn-primary primaryLive'
    #set $href = '#'
    #end if
    <a class="btn${classlist}" href="$href">$gettext($graphMenuItem['text'])</a>
    #end for
</p>
<script type="text/javascript">
## 'raw' makes Cheetah skip this section so it doesn't get confused by the dollar characters in the js
#raw
    let graphMenu = document.getElementById("graphMenu");
    if(graphMenu !== null && graphMenu !== undefined) {
      document.getElementById("indexHtml").classList.add("active");
      let listItems = document.evaluate("a", graphMenu, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
      for(let i = 0; i < listItems.snapshotLength; i++) {
        let item = listItems.snapshotItem(i);
        if(window.innerWidth < 768) {
          let hash = item.href.endsWith('#') ? '' : '#';
          item.href += hash + "menu";
        }
      }
    }
#end raw
</script>
