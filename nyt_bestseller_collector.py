import click
import requests
import json
import os
from time import sleep
from datetime import date, datetime, timedelta

API_KEY = os.getenv('NYT_API_KEY')
HOST = "https://api.nytimes.com"

def make_api_request(url, additional_params, retries=10):
    params_with_key = {'api-key': API_KEY}
    params_with_key.update(additional_params)
    r = requests.get(url, params=params_with_key)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 429 and retries > 0:
        sleep(6)
        return make_api_request(url, additional_params, retries - 1)
    
    print("Request failed", additional_params, url)
    print(r.headers)
    print(r.json())
    raise Exception("Request failed")

def get_overview(published_date: datetime):
    url = HOST + "/svc/books/v3/lists/full-overview.json"
    return  make_api_request(url, {'published_date': date_to_str(published_date)})

def first_time_on_list(list, book):
    # monthly books have a lowest weeks_on_list of 0
    # weekly  books have a lowest weeks_on_list of 1
    # This is an error in NYT API, in future monthly books may have weeks_on_list of 1 as a minimum
    if list.get("updated") == "WEEKLY":
        return book.get('weeks_on_list') == 1
    if list.get("updated") == "MONTHLY":
        return book.get('weeks_on_list') == 0

def process_overview_response_reviews(response):
    """
    Get all the reviews from an overview response
    """
    outputs = {}
    for list in response.get('results').get('lists'):
        for book in list.get('books'):
            isbn = book.get('primary_isbn13', "")
            isbn = isbn if len(isbn) == 13 else book['primary_isbn10']
            reviews = set(outputs.get(isbn, {}).get('reviews', []))

            if book.get('book_review_link'):
                reviews.add(book.get('book_review_link'))
            if book.get('sunday_review_link'):
                reviews.add(book.get('sunday_review_link'))

            if len(reviews) > 0:
                # we convert back to a list because we need to serialize
                outputs[isbn] = {'reviews': [x for x in reviews], 'isbn': isbn}
    return outputs
            

def process_overview_response(response: dict, seen_isbns: set):
    outputs = []
    published_date = response.get('results').get('published_date')
    print(f"Processing date: {published_date}")
    for list in response.get('results').get('lists'):
        list_data = {
            'list_name_encoded': list['list_name_encoded'],
            'published_date': published_date,
            'isbns': []
        }
        for book in list.get('books'):
            # only get books that are on the list for the first time
            if first_time_on_list(list, book):
                # we prefer isbn 13 but if that is not available we will use isbn 10
                isbn = book.get('primary_isbn13', "")
                isbn = isbn if len(isbn) == 13 else book['primary_isbn10']
                # we need to track seen isbns because monthly lists don't update "weeks_on_list" each week
                if isbn not in seen_isbns:
                    list_data['isbns'].append(isbn)
                    seen_isbns.add(isbn)
        outputs.append(list_data)
    print(sum([len(x.get('isbns')) for x in outputs]), "new books")
    return outputs

def write_result_to_disk(outputs, output_file: str):
    with open(output_file, 'w') as fp:
        json.dump(outputs, fp)
    print(f"results written to {output_file}")

def date_to_str(date: datetime):
    return date.strftime('%Y-%m-%d')

@click.command()
@click.option('--output_file', default="result.json", help='Where to write the results')
@click.option('--date-start', type=click.DateTime(formats=["%Y-%m-%d"]),
              default=str(date.today() - timedelta(30)), help='Date to start adding books from. Defaults to 30 days ago')
@click.option('--date-end', type=click.DateTime(formats=["%Y-%m-%d"]),
              default=str(date.today()), help='Date to stop adding books from. Defaults to today.')
def run_with_click(output_file, date_start, date_end):
    current_date = date_start + timedelta(days=0)
    outputs = []
    reviews = {}
    seen_isbns = set()
    while current_date <= date_end:
        overview = get_overview(current_date)
        outputs.extend(process_overview_response(overview, seen_isbns))
        reviews.update(process_overview_response_reviews(overview))
        current_date = current_date + timedelta(days=7)

    write_result_to_disk(outputs, output_file)
    write_result_to_disk(reviews, 'reviews.json')
    print(f"{len(seen_isbns)} total books found between {date_start} and {date_end}")

if __name__ == "__main__":
    run_with_click()
