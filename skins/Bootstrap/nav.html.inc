<nav class="navbar sticky-top navbar-expand bg-dark" data-bs-theme="dark">
    <div class="container-fluid">
        #set $station_url = $station.station_url
        #if "location_href" in $Extras and $Extras.location_href != ''
            #set $station_url = $Extras.location_href
        #end if
        <div class="d-none d-md-inline"><a class="navbar-brand" href="$station_url">$station.location</a></div>
        <div class="navbar-collapse">
            <ul id="navbarList" class="navbar-nav nav-fill d-flex justify-content-center col-8 col-md-auto">
                #for $nav_item in $Navigation['navigation_items']
                #set $active = ''
                #set $href = $Navigation[$nav_item]['href']
                #if $nav_item in $filename
                #set $active = ' active'
                #set $href = '#'
                #end if
                #set $hrefTitle = ''
                #if 'title' in $Navigation[$nav_item]
                #set $hrefTitle = $Navigation[$nav_item]['title']
                #end if
                #set $extraLinkAttributes = ''
                #set $listItemClasses = 'nav-item'
                #set $linkClasses = 'nav-link' + $active
                #if 'navigation_items' in $Navigation[$nav_item]
                #set $extraLinkAttributes = 'data-bs-toggle="dropdown" role="button" aria-expanded="false"'
                #set $listItemClasses = $listItemClasses + ' dropdown'
                #set $linkClasses  = $linkClasses  + ' dropdown-toggle'
                #end if
                <li class="$listItemClasses">
                    <a id="${nav_item}Html" class="$linkClasses" href="$href" title="$gettext($hrefTitle)" $extraLinkAttributes>
                    #set $icon = 'bi-file-x'
                    #if 'icon' in $Navigation[$nav_item]
                    #set $icon = $Navigation[$nav_item]['icon']
                    #end if
                    <i class="$icon fs-2 d-inline d-md-none" title="$gettext($Navigation[$nav_item]['text'])"></i>
                    <span class="d-none d-md-inline">$gettext($Navigation[$nav_item]['text'])</span>
                    </a>
                    ## Submenu Items
                    #if 'navigation_items' in $Navigation[$nav_item]
                    <ul class="dropdown-menu">
                      #for $nav_sub_item in $Navigation[$nav_item]['navigation_items']
                      #set $href = $Navigation[$nav_item][$nav_sub_item]['href']
                      #set $hrefTitle = ''
                      #if 'title' in $Navigation[$nav_item][$nav_sub_item]
                      #set $hrefTitle = $Navigation[$nav_item][$nav_sub_item]['title']
                      #end if
                      <li><a id="${nav_sub_item}Html" class="dropdown-item" href="$href" title="$gettext($hrefTitle)">
                      $gettext($Navigation[$nav_item][$nav_sub_item]['text'])
                      </a></li>
                      #end for
                    </ul>
                    #end if
                </li>
                #end for
            </ul>
            #set $msAuto = ' ms-auto'
            #if $varExists('TranslationLinks')
            <ul id="navbarLang" class="navbar-nav${msAuto} me-4">
              <li class="dropdown nav-item">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
                  $lang
                </a>
                <ul class="dropdown-menu">
                  #set $i = 0
                  #for $link in $TranslationLinks
                  <li><a class="dropdown-item" href="$TranslationLinks[$link]/$filename">$link</a></li>
                  #set $i = $i + 1
                  #end for
                </ul>
              </li>
            </ul>
            #set $msAuto = ''
            #end if
            <div class="navbar-text d-none d-lg-inline${msAuto}">$gettext("Last update") <span id="lastUpdate">$current.dateTime</span></div>
        </div>
    </div>
</nav>
