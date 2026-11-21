#set $graphMenuItems = [{'view': 'live', 'text': 'Live'}, {'view': 'day', 'text': 'Day'}, {'view': 'week', 'text': 'Week'}, {'view': 'month', 'text': 'Month'}, {'view': 'year', 'text': 'Year'}]
#set $onIndexPage = 'index.html' in $filename
<section id="menu"></section>
<p id="graphMenu" class="my-1 mt-md-0">
    #for $graphMenuItem in $graphMenuItems
    #set $classlist = ' btn-light primaryLight'
    #if $graphMenuItem['view'] == 'live' and $onIndexPage
    #set $classlist = ' btn-primary primaryLive'
    #end if
    #if $graphMenuItem['view'] == 'live'
    #set $href = 'index.html'
    #elif $onIndexPage
    #set $href = '#' + $graphMenuItem['view']
    #else
    #set $href = 'index.html#' + $graphMenuItem['view']
    #end if
    <a class="btn${classlist}" href="$href" data-view="$graphMenuItem['view']">$gettext($graphMenuItem['text'])</a>
    #end for
</p>
<script type="text/javascript">
## 'raw' makes Cheetah skip this section so it doesn't get confused by the dollar characters in the js
#raw
    let graphMenu = document.getElementById("graphMenu");
    if(graphMenu !== null && graphMenu !== undefined) {
      document.getElementById("indexHtml").classList.add("active");
    }
#end raw
</script>
