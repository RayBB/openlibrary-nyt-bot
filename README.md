# openlibrary-nyt-bot-temp
A temporary repo while actively developing the nyt bot for Open Library

`main2.py` is current version of getting data from nyt api. Just uses overview api. The oldest data available from overview api is from `2008-06-02`.

`add_nyt_bestseller_tag.py` is the code to actually add the nyt to the works.

`main.py` can be ignored. Was my first pass at getting data from NYT API. However, it turns out the history endpoint is buggy (doesn't work for some ISBNs that were retrieved from the lists endpoint). 

## Setup

1. Install requirements `pip install -r requirements.txt`
1. Set the environment variable `NYT_API_KEY` to be able to call the NYT API
1. [Configure](https://github.com/internetarchive/openlibrary-client#configuration) Open Library CLI
1. Run `python nyt_bestseller_collector.py` - this will get the bestsellers for this week and put them in `result.json`
1. Run `python add_nyt_bestseller_tag.py --file=result.json --dry-run=True` to add

## Bulk Imports

NYT bot was run in August 2021 to do bulk imports for the following historical data:
* [nyt_bestsellers_2008_06_03_to_2021_08_03](https://archive.org/details/nyt_bestsellers_2008_06_03_to_2021_08_03) - scraped from public api via script here.
* [all_nyt_book_review_2021_08_03](https://archive.org/details/all_nyt_book_review_2021_08_03) - using a NYT database dump since public apis don't make it easy to get old data.

### Stats

#### Best Sellers
* Best Sellers From NYT API: 20,946
* Best Sellers missing from Open Library: 3,955
* Missing bestsellers successfully imported: 370
* Subject tags added to all books found in Open Library

#### Reviews
* Reviews From NYT API: 24,975
* Reviews missing from Open Library: 2,889
* Missing reviewed books successfully imported: 1,435
* Subject tag and link added to all books found in open library

## Future Plans

1. Run the best seller scraper then import that data once per week (preferably on wednesdays when list is released). I recommend scraping the last month just to double check if books may be importable at later times.
2. For reviews... well there is no way to get all reviews. But we can get reviews of bestsellers. So that will be made part of the scrape for bestsellers.

## Testing

Testing checklist for bestsellers:
If no nyt subjects exist, add them ✅
If both nyt subjects exist, make no change ✅
If one nyt subject is missing, add the other - not yet


Testing checklist for review bot:
If review doesn't exist, add it ✅
If review subject doesn't exist, add it ✅
