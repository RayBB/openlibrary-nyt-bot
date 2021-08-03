# openlibrary-nyt-bot-temp
A temporary repo while actively developing the nyt bot for Open Library

`main.py` was my first pass at getting data from NYT API. However, it turns out the history endpoint is buggy (doesn't work for some ISBNs that were retrieved from the lists endpoint).

`main2.py` is an iteration that's much simpler just using one call to the overview endpoint.
