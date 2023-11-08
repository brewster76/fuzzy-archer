    <hr>
    <footer>
        #if $gettext("Footer text") == "Footer text"
        <p class="footer"><a href='https://github.com/brewster76/fuzzy-archer'>fuzzy-archer</a> version $fuzzy_archer_version, powered by <a href='https://weewx.com'>WeeWX</a></p>
        #else
        <p>$gettext("Footer text")</p>
        #end if
    </footer>