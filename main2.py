import click
import requests
import json
import os

API_KEY = os.getenv('NYT_API_KEY')

def make_api_request(url, additional_params):
    params_with_key = {
        'api-key': API_KEY
    }
    params_with_key.update(additional_params)
    r = requests.get(url, params=params_with_key)
    return r.json()

def get_overview(published_date: str):
    url = "https://api.nytimes.com/svc/books/v3/lists/full-overview.json"
    return  make_api_request(url, {'published_date': published_date})

def process_overview_response(response: dict):
    outputs = []
    published_date = response.get('results').get('published_date')
    print(f"Processing date: {published_date}")
    print(len(response.get('results').get('lists')), "lists")
    for list in response.get('results').get('lists'):
        list_data = {
            'list_name_encoded': list['list_name_encoded'],
            'published_date': published_date,
            'isbns': []
        }
        for book in list.get('books'):
            # only get books that are on the list for the first time
            if (book['weeks_on_list'] == 0):
                # we prefer isbn 13 but if that is not available we will use isbn 10
                isbn = book.get('primary_isbn13', "")
                isbn = isbn if len(isbn) == 13 else book['primary_isbn10']
                list_data['isbns'].append(isbn)
        outputs.append(list_data)
    print(sum([len(x.get('isbns')) for x in outputs]), "new books")
    return outputs

def write_result_to_disk(outputs, output_file: str):
    with open(output_file, 'w') as fp:
        json.dump(outputs, fp)
    print(f"results written to {output_file}")

@click.command()
@click.option('--output_file', default="result.json", help='Where to write the results')
@click.option('--published_date', default="", help='Date in YYYY-MM-DD format to add books from. Defaults to today.')
def run_with_click(output_file, published_date):
    overview = get_overview(published_date)
    outputs = process_overview_response(overview)
    write_result_to_disk(outputs, output_file)

if __name__ == "__main__":
    run_with_click()
