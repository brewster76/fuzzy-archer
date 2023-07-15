<nav aria-label="Nav" class="navbar navbar-expand-lg bg-dark" data-bs-theme="dark">
    <div class="container-fluid">
        #set $station_url = $station.station_url
        #if "location_href" in $Extras and $Extras.location_href != ''
            #set $station_url = $Extras.location_href
        #end if
        <a class="navbar-brand" href="$station_url">$station.location</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarText"
                aria-controls="navbarText" aria-expanded="false" aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarText">
            <ul id="navbarList" class="navbar-nav mb-2 mb-lg-0">
                #for $nav_item in $Navigation['navigation_items']
                <li class="nav-item">
                    <a id="${nav_item}Html" class="nav-link" href="$Navigation[$nav_item]['href']">$gettext($Navigation[$nav_item]['text'])</a>
                </li>
                #end for
            </ul>
            #if $varExists('TranslationLinks')
            <ul id="navbarLang" class="navbar-nav ms-auto mb-2 mb-lg-0 me-4">
              <li class="dropdown nav-item">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown" aria-expanded="false">
                  $lang
                </a>
                <ul class="dropdown-menu">
                  #set $i = 0
                  #for $link in $TranslationLinks
                  <li><a class="dropdown-item" href="$TranslationLinks[$link]">$link</a></li>
                  #set $i = $i + 1
                  #end for
                </ul>
              </li>
            </ul>
            #end if
            <div class="navbar-text">$gettext("Last update") <span id="lastUpdate">$current.dateTime</span></div>
        </div>
    </div>
    <script type="text/javascript">
    ## 'raw' makes Cheetah skip this section so it doesn't get confused by the dollar characters in the js
    #raw
        let href = window.location.href;

        if(href.endsWith("/")) {
            document.getElementById("indexHtml").classList.add("active");
        } else {
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
        }
    #end raw
    </script>
</nav>
