<nav aria-label="Nav" class="navbar navbar-expand-lg navbar-dark bg-dark">
    <div class="container-fluid">
        <a class="navbar-brand" href="https://de.wikipedia.org/wiki/Hallein">$station.location</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarText"
                aria-controls="navbarText" aria-expanded="false" aria-label="Toggle navigation">
            <span class="navbar-toggler-icon"/>
        </button>
        <div class="collapse navbar-collapse" id="navbarText">
            <ul id="navbarList" class="navbar-nav me-auto mb-2 mb-lg-0">
                <li class="nav-item">
                    <a id="indexHtml" class="nav-link" href="index.html#">The Weather<span
                            class="visually-hidden">(current)</span>
                    </a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="stats.html">Stats</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="history.html">History</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="news.html">News</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="about.html">About</a>
                </li>
            </ul>
            <span class="navbar-text">Last update<span id="lastUpdate"> $current.dateTime</span>
      </span>
        </div>
    </div>
</nav>