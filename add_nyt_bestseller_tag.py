"""
A bot to add a NYT bestseller tags 'nyt:{list_name_encoded}={published_date}'
and 'New York Times bestseller' to each book from the list of ISBNs.

The list of bestsellers to add is a json file of the following format:
[
    {
        "list_name_encoded": "business-books",
        "published_date": "2020-07-12",
        "isbns": [
            "9780735211292",
            "9780399592522"
        ]
    },
]
This script would be called from the command line like so:
$ python3 add_nyt_bestseller_tag.py --file=~/nyt_bstslrs.json --dry-run=True
NOTE: This script checks if there is a tag on a book that starts with
'nyt:' and if the book has such a tag the script does nothing.
If there is no such book with requested isbn in the OL, the script makes request
by the book isbn https://openlibrary.org/isbn/{isbn} , triggering auto import
"""

import json
from signal import signal, SIGINT
import logging
import os

import requests
from olclient.bots import AbstractBotJob
from olclient import OpenLibrary, config
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env

class AddNytBestsellerJob(AbstractBotJob):
    NYT_TAG_PREFIX = 'nyt:'
    NYT_TAG_BESTSELLER = 'New York Times bestseller'
    OL_IMPORT_URL_TEMPLATE = 'https://openlibrary.org/isbn/{}'

    def __init__(self):
        super().__init__(job_name='AddNytBestseller')
        # You can change this to logging.DEBUG if you want to see all logs
        self.logger.setLevel(logging.INFO)

    def __need_to_add_nyt_bestseller_tag(self, work) -> bool:
        """Returns False if the book already has
        a tag that starts with 'nyt:'"""
        try:
            subjects_to_add = (self.NYT_TAG_PREFIX, self.NYT_TAG_BESTSELLER)
            return not any(subj.startswith(subjects_to_add) for subj in work.subjects)
        except AttributeError:
            self.logger.debug(f'Failed to check subjects for work {work.olid}, no subject list exist')
            return True

    def __add_tags(self, work, new_tags) -> None:
        """Adds a new tag to a work"""
        try:
            work.subjects.extend(new_tags)
        except AttributeError:
            work.subjects = new_tags

    def __request_book_import_by_isbn(self, book_isbn) -> None:
        """ Makes request to the book_isbn endpoint to attempt automatic import
        https://openlibrary.org/isbn/{book_isbn} """
        url = self.OL_IMPORT_URL_TEMPLATE.format(book_isbn)
        try:
            if not self.dry_run:
                requests.get(url)
        except Exception as e:
            self.logger.error(f'Failed to make request to {url}')

    def __save_job_results(self, job_results) -> None:
        self.logger.info(f'Job execution results: {repr(job_results)}')
        with open('results/add_nyt_bestseller_result.json', 'w', encoding='utf-8') as f:
            json.dump(job_results, f, ensure_ascii=False, indent=4)

    def __process_found_bestseller_edition(self, bstslr_record_isbn,
        bstslr_edition, new_tags, comment, job_results) -> None:
        if not bstslr_edition.work:
            raise Exception(f'No work found for the edition with isbn {bstslr_record_isbn}')
        if self.__need_to_add_nyt_bestseller_tag(bstslr_edition.work):
            self.logger.info(
                f'The NYT tags to be added for the work {bstslr_edition.work.olid} of the edition {bstslr_record_isbn}')
            work = bstslr_edition.work
            self.__add_tags(work, new_tags)
            self.save(lambda: work.save(comment=comment))
            job_results['tags_added'] += 1
        else:
            self.logger.debug(f'A NYT tag already exists for the work {bstslr_edition.work.olid} of the edition {bstslr_record_isbn}')
            job_results['tags_already_exist'] += 1

    def __process_bestseller_group_record(self, bestseller_group_record, comment, job_results) -> None:
        new_tags = ['{}{}={}'.format(
            self.NYT_TAG_PREFIX,
            bestseller_group_record['list_name_encoded'],
            bestseller_group_record['published_date']),
            self.NYT_TAG_BESTSELLER]
        for bstslr_record_isbn in bestseller_group_record['isbns']:
            try:
                bstslr_edition = self.ol.Edition.get(isbn=bstslr_record_isbn)
                if bstslr_edition:
                    self.__process_found_bestseller_edition(bstslr_record_isbn, bstslr_edition, new_tags, comment, job_results)
                else:
                    self.logger.debug(f'The edition {bstslr_record_isbn} doesn\'t exist in OL, importing')
                    self.__request_book_import_by_isbn(bstslr_record_isbn)
                    job_results['books_imported'] += 1
                    job_results['books_imported_isbns'].append(bstslr_record_isbn)
            except SystemExit:
                self.logger.info(f'Interrupted the bot while processing ISBN {bstslr_record_isbn}')
                job_results['isbns_failed'] += 1
                self.__save_job_results(job_results)
                raise
            except:
                self.logger.exception(f'Failed to process ISBN {bstslr_record_isbn}')
                job_results['isbns_failed'] += 1
            job_results['total_books_processed'] += 1
            # the update() function adds one to the progress bar
            self.__progress_bar.update(1)

    def run(self) -> None:  # overwrites the AbstractBotJob run method
        self.dry_run = self.args.dry_run
        # limit could be set to 1 to only change the first book
        self.limit = None
        self.dry_run_declaration()
        comment = 'Add NYT bestseller tag'
        file_location = self.args.file if self.args.file is not None else 'results/bestseller_collection_results.json'
        with open(file_location, 'r') as f:
            bestsellers_data = json.load(f)['bestsellers']

        total_books = sum([len(i['isbns']) for i in bestsellers_data])

        job_results = {'input_file': self.args.file,
                        'total_books_to_process': total_books,
                        'total_books_processed': 0,
                        'books_imported': 0, 'books_imported_isbns': [],
                       'tags_added': 0, 'tags_already_exist': 0, 'isbns_failed': 0, 'dry_run': self.dry_run}
        self.__progress_bar = tqdm(total=total_books, unit='books')

        for bestseller_group_record in bestsellers_data:
            self.__process_bestseller_group_record(bestseller_group_record, comment, job_results)
        self.__save_job_results(job_results)


def handler(signal_received, frame):
    msg = 'SIGINT or CTRL-C detected. Interrupting the bot'
    job.logger.info(msg)
    exit(0)


if __name__ == "__main__":
    signal(SIGINT, handler)
    job = AddNytBestsellerJob()
    if 'OL_ACCESS_KEY' in os.environ and 'OL_SECRET_KEY' in os.environ:
        job.ol = OpenLibrary(credentials=config.Credentials(access=os.environ.get('OL_ACCESS_KEY'),
                                                            secret=os.environ.get('OL_SECRET_KEY')))

    try:
        job.run()
    except Exception as e:
        job.logger.exception("The AddNytBestsellerJob thrown an exception")
        raise e
