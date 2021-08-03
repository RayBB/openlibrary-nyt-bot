import requests
import json
import os
from datetime import datetime
from time import sleep

API_KEY = os.getenv('NYT_API_KEY')
NYT_TIMEOUT = 6 #how many seconds to sleep between NYT API requests - default is 6 seconds

'''

1. Get all the books for a list
2. Get the history for each book

From the history get:
isbns - a list of isbns to try to use since there are often multiple
list it was first published on
    if a tie just pick randomly for now
date it was first published on the list

write the above to a CSV
Print out number of books that need to be added

'''

def make_api_request(url, additional_params):
    params_with_key = {
        'api-key': API_KEY
    }
    params_with_key.update(additional_params)
    r = requests.get(url, params=params_with_key)
    sleep(NYT_TIMEOUT)
    return r.json()

def get_list(list_type: str, date: str):
    url = "https://api.nytimes.com/svc/books/v3/lists.json"
    return  make_api_request(url, {'list': list_type,'published-date': date})

def get_history(isbn: str):
    url = "https://api.nytimes.com/svc/books/v3/lists/best-sellers/history.json"
    return  make_api_request(url, {'isbn': isbn})

def process_history_response(response_json):
    results = response_json.get('results', [])

    if (len(results) == 0):
        print("no history results found")
        print(response_json)
        return None
    
    selected_list = choose_bestseller_list(results)
    out = {}
    out['alternative_isbns'] = get_isbns(results[0])
    out['primary_isbn'] = selected_list.get('primary_isbn13')
    out['list_name'] = selected_list.get('list_name')
    out['bestsellers_date'] = selected_list.get('bestsellers_date')
    return out
    
    
'''
Input:
{
    "isbns": 
    [
        {"isbn10": "0385544189", "isbn13": "9780385544184"},
        {"isbn10": "0525639365", "isbn13": "9780525639367"}
    ]
}
'''
def get_isbns(result):
    isbns = []
    for isbn_pair in result.get('isbns', []):
        # I this field can be set to "None" by NYT api so we are checking length before adding
        if len(isbn_pair.get('isbn10')) == 10:
            isbns.append(isbn_pair.get('isbn10'))
        if len(isbn_pair.get('isbn13')) == 13:
            isbns.append(isbn_pair.get('isbn13'))
    return isbns

'''
A book may be on many best seller lists
For our purposes we will choose the oldest (but first published)
If there is a tie then choose the shortest list name - this is to bias against the long "combined" list names
If there is a tie choose randomly
'''
def choose_bestseller_list(results):
    rank_history = results[0].get('ranks_history')
    oldest_lists = get_oldest_bestseller_lists(rank_history)
    shortest_lists = get_bestseller_lists_shortest_name(oldest_lists)
    # if there happens to be a tie we'll just return the first one for now
    return shortest_lists[0]


'''
Given a list of rankings, it will return the oldest ones
'''
def get_oldest_bestseller_lists(rank_history):
    oldest_date = strToDate(rank_history[0].get('bestsellers_date'))
    for rank in rank_history:
        oldest_date = min([oldest_date, strToDate(rank.get('bestsellers_date'))])
    return list(filter(lambda x : x.get('bestsellers_date') == dateToStr(oldest_date), rank_history))

def get_bestseller_lists_shortest_name(rank_history):
    shortest_list_name_length = len(rank_history[0].get('list_name'))
    for rank in rank_history:
        oldest_date = min([shortest_list_name_length, len(rank.get('list_name'))])
    return list(filter(lambda x : len(x.get('list_name')) == shortest_list_name_length, rank_history))

def strToDate(date_string):
    return datetime.fromisoformat(date_string)

def dateToStr(date: datetime):
    return date.strftime('%Y-%m-%d')

if __name__ == "__main__":
    list_name = 'hardcover-fiction'
    published_date = '2020-02-01'
    output_file = 'result.json'
    books_to_get = 1
    list_response =  get_list(list_name, published_date)
    out = []
    for result in list_response.get('results'):
        isbn = result.get('book_details')[0].get('primary_isbn13')
        print(f"getting {isbn}")
        history_json  = get_history(isbn)
        result = process_history_response(history_json)
        out.append(result)
        books_to_get -= 1
        if books_to_get == 0:
            break
    
    with open(output_file, 'w') as fp:
        json.dump(out, fp)
    print(f"done - see {output_file}")