"""
A bot to add a NYT review link to the links array for a work
 {'title': '"It\'s a steal" (NYT review)',
   'url': 'https://www.nyt.com/books/2007/jan/06/featuresreviews',
   'type': {'key': '/type/link'}}
 each book from the list of ISBNs.

The list of reviews to add is a json file of the following format:
[
    [
        "http://www.nytimes.com/1981/01/05/books/books-of-the-times-210615.html",
        "9780140063134"
    ],
]
This script would be called from the command line like so:
$ python3 add_nyt_review_link.py --file=~/nyt_reviews.json --dry-run=True
NOTE: This script checks if there is a link in the links with the same URL
If there is no such book with requested isbn in the OL, the script makes request
by the book isbn https://openlibrary.org/isbn/{isbn} , triggering auto import
"""

import json
import os
from signal import signal, SIGINT
import logging

import requests
from olclient import OpenLibrary, config
from olclient.bots import AbstractBotJob
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env


class AddNytReviewJob(AbstractBotJob):
    URL_STARTS_WITH = 'http'
    NYT_REVIEW_DEFAULT_TITLE = 'New York Times review'
    NYT_TAG_REVIEWED = 'New York Times reviewed'
    OL_LINK_TYPE_KEY_VALUE = '/type/link'
    OL_IMPORT_URL_TEMPLATE = 'https://openlibrary.org/isbn/{}'

    def __init__(self):
        super().__init__(job_name='AddNytReviewJob')
        self.job_results = {'input_file': self.args.file, 'books_imported': 0, 'links_added': 0,
                            'links_already_exist': 0, 'isbns_failed': 0, 'dry_run': self.dry_run,
                            'subjects_added': 0, 'subjects_already_exist': 0}

        # You can change this to logging.DEBUG if you want to see all logs
        self.logger.setLevel(logging.INFO)

    def __need_to_add_nyt_review_link(self, work, link) -> bool:
        """Returns False if the book already has
        the same link in the links section"""
        try:
            for lnk in work.links:
                if lnk.get('url', '').startswith(link):
                    return False
            return True
        except AttributeError:
            self.logger.debug(f'Failed to check link for work {work.olid}, no links list exist')
            return True

    def __add_link(self, work, url) -> None:
        """Adds a new link to a work"""
        if not self.__need_to_add_nyt_review_link(work, url):
            self.logger.debug(f'A NYT link already exists for the work {work.olid}')
            self.job_results['links_already_exist'] += 1
            return None

        link_struct = self.__generate_new_link(url)
        try:
            # check if there is an http version of the same link, if so update it.
            for link in work.links:
                if link.get('url') == url.replace('https://', 'http://'):
                    link['url'] = url
                    self.logger.debug(f'Successfully updated NYT review with https for work {work.olid}')
                    return None

            work.links.append(link_struct)
        except AttributeError:
            work.links = [link_struct]

        self.job_results['links_added'] += 1
        self.logger.debug(f'Successfully appended new link with NYT review to work {work.olid}')

    def __request_book_import_by_isbn(self, book_isbn) -> None:
        """ Makes request to the book_isbn
        https://openlibrary.org/isbn/{book_isbn} """
        url = self.OL_IMPORT_URL_TEMPLATE.format(book_isbn)
        try:
            if not self.dry_run:
                requests.get(url)
            self.logger.info(f'Made request to {url}')
        except Exception as e:
            self.logger.error(f'Failed to make request to {url}')
        self.job_results['books_imported'] += 1

    def __save_job_results(self) -> None:
        self.logger.info(f'Job execution results: {repr(self.job_results)}')
        with open('results/add_nyt_review_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.job_results, f, ensure_ascii=False, indent=4)

    def __add_bestseller_review_tag(self, work, subject_to_add: str):
        """Adds a tag to the work if it is a bestseller"""
        try:
            if subject_to_add not in work.subjects:
                work.subjects.append(subject_to_add)
                self.job_results['subjects_added'] += 1
            else:
                self.job_results['subjects_already_exist'] += 1
        except:
            work.subjects = [subject_to_add]
            self.job_results['subjects_added'] += 1

    def __process_found_bestseller_edition(self, bstslr_record_isbn, bstslr_edition, review_urls, comment) -> None:
        if not bstslr_edition.work:
            raise Exception(f'No work found for the edition with isbn {bstslr_record_isbn}')
        work = bstslr_edition.work
        self.__add_bestseller_review_tag(work, self.NYT_TAG_REVIEWED)
        [self.__add_link(work, url) for url in review_urls]
        self.save(lambda: work.save(comment=comment))

    def __generate_new_link(self, url):
        return {
            'url': url,
            'title': self.NYT_REVIEW_DEFAULT_TITLE,
            'type': {
                'key': self.OL_LINK_TYPE_KEY_VALUE
            }
        }
    def __process_review_record(self, review_record, comment) -> None:
        review_record_isbn = review_record.get('isbn')
        try:
            bstslr_edition = self.ol.Edition.get(isbn=review_record_isbn)
            if bstslr_edition:
                review_urls = review_record.get('reviews')
                self.__process_found_bestseller_edition(review_record_isbn, bstslr_edition, review_urls, comment)
            else:
                self.logger.debug(f'The edition {review_record_isbn} doesnt exist in OL, importing')
                self.__request_book_import_by_isbn(review_record_isbn)
        except SystemExit:
            self.logger.info(f'Interrupted the bot while processing ISBN {review_record_isbn}')
            self.job_results['isbns_failed'] += 1
            self.__save_job_results()
            raise
        except:
            self.logger.exception(f'Failed to process ISBN {review_record_isbn}')
            self.job_results['isbns_failed'] += 1

    def run(self) -> None:  # overwrites the AbstractBotJob run method
        self.dry_run = self.args.dry_run
        self.limit = None
        self.dry_run_declaration()
        comment = 'Add NYT review links'
        file_location = self.args.file if self.args.file is not None else 'results/bestseller_collection_results.json'
        with open(file_location, 'r') as f:
            review_record_array = list(json.load(f)['reviews'].values())
            for review_record in tqdm(review_record_array, unit='reviews'):
                self.__process_review_record(review_record, comment)
        self.__save_job_results()


def handler(signal_received, frame):
    msg = 'SIGINT or CTRL-C detected. Interrupting the bot'
    job.logger.info(msg)
    exit(0)


if __name__ == "__main__":
    signal(SIGINT, handler)
    job = AddNytReviewJob()
    if 'OL_ACCESS_KEY' in os.environ and 'OL_SECRET_KEY' in os.environ:
        job.ol = OpenLibrary(credentials=config.Credentials(access=os.environ.get('OL_ACCESS_KEY'),
                                                            secret=os.environ.get('OL_SECRET_KEY')))

    try:
        job.run()
    except Exception as e:
        job.logger.exception("The AddNytReviewJob thrown an exception")
        raise e
