# openlibrary-nyt-bot-temp
A temporary repo while actively developing the NYT bot for Open Library.

The bot has three primary goals:
1. Notify Open Library of new books that they may not have imported yet
2. Tag NYT best sellers and reviews
3. Add links to NYT reviews

## Setup

1. Install requirements `pip install -r requirements.txt`
2. Set the environment variable `NYT_API_KEY` to be able to call the NYT API
3. [Configure](https://github.com/internetarchive/openlibrary-client#configuration) Open Library CLI
   1. Alternatively, set `OL_ACCESS_KEY` and `OL_SECRET_KEY` env vars
4. Run `python nyt_bestseller_collector.py` - this will get the bestsellers for this week and put them in `result.json`
5. Run `python add_nyt_bestseller_tag.py --dry-run=False` to add the bestseller tags
6. Run `python add_nyt_review_link.py --dry-run=False` to add reviews

`.env` file is supported and probably the easiest way to set env vars

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

1. Run the bestseller scraper then import that data once per week (preferably on wednesdays when list is released). 
I recommend scraping the last month just to double check if books may be importable at later times.
2. For reviews... well there is no way to get all reviews. But we can get reviews of bestsellers. 
So that will be made part of the scrape for bestsellers.

## Testing

Testing checklist for bestsellers:
If no nyt subjects exist, add them ✅
If both nyt subjects exist, make no change ✅
If one nyt subject is missing, add the other - not yet


Testing checklist for review bot:
If review doesn't exist, add it ✅
If review subject doesn't exist, add it ✅
