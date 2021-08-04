# openlibrary-nyt-bot-temp
A temporary repo while actively developing the nyt bot for Open Library

`main2.py` is current version of getting data from nyt api. Just uses overview api. The oldest data available from overview api is from `2008-06-02`.

`add_nyt_bestseller_tag.py` is the code to actually add the nyt to the works.

`main.py` can be ignored. Was my first pass at getting data from NYT API. However, it turns out the history endpoint is buggy (doesn't work for some ISBNs that were retrieved from the lists endpoint). 
