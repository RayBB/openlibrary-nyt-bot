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
$ python3 add_nyt_review.py --file=~/nyt_reviews.json --dry-run=True
NOTE: This script checks if there is a link in the links with the same URL
If there is no such book with requested isbn in the OL, the script makes request
by the book isbn https://openlibrary.org/isbn/{isbn} , triggering auto import
"""

import json
from signal import signal, SIGINT

import requests
from olclient.bots import AbstractBotJob
from tqdm import tqdm


class AddNytReviewJob(AbstractBotJob):
    URL_STARTS_WITH = 'http'
    NYT_REVIEW_DEFAULT_TITLE = 'New York Times review'
    NYT_TAG_REVIEWED = 'New York Times reviewed'
    OL_LINK_TYPE_KEY_VALUE = '/type/link'
    OL_IMPORT_URL_TEMPLATE = 'https://openlibrary.org/isbn/{}'

    def __init__(self):
        super().__init__(job_name='AddNytReviewJob')

    def __need_to_add_nyt_review_link(self, work, link) -> bool:
        """Returns False if the book already has
        the same link in the links section"""
        try:
            for lnk in work.links:
                if lnk.get('url', '').startswith(link):
                    return False
            return True
        except AttributeError:
            self.logger.info(
                'Failed to check link for work {}, no links list exist'
                    .format(work.olid))
            return True

    def __add_link(self, work, link_struct) -> None:
        """Adds a new link to a work"""
        try:
            # check if there is an http version of the same link, if so update it.
            for lnk in work.links:
                if lnk.get('url') == link_struct['url'].replace('https://', 'http://'):
                    lnk['url'] = link_struct['url']
                    self.logger.info(
                        'Successfully updated NYT review with https for work {}'
                            .format(work.olid))
                    return None

            work.links.append(link_struct)
            self.logger.info(
                'Successfully appended new link with NYT review to work {}'
                    .format(work.olid))
        except AttributeError:
            work.links = [link_struct]

    def __request_book_import_by_isbn(self, book_isbn) -> None:
        """ Makes request to the book_isbn
        https://openlibrary.org/isbn/{book_isbn} """
        url = self.OL_IMPORT_URL_TEMPLATE.format(book_isbn)
        try:
            if not self.dry_run:
                requests.get(url)
            self.logger.info('Made request to {}'.format(url))
        except Exception as e:
            self.logger.error('Failed to make request to {}'.format(url))

    def __save_job_results(self, job_results) -> None:
        self.logger.info('Job execution results: {}'.format(repr(job_results)))
        with open('add_nyt_review_result.json', 'w', encoding='utf-8') as f:
            json.dump(job_results, f, ensure_ascii=False, indent=4)

    def __add_bestseller_review_tag(self, work, subject_to_add: str, job_results):
        """Adds a tag to the work if it is a bestseller"""
        try:
            if subject_to_add not in work.subjects:
                work.subjects.append(subject_to_add)
                job_results['subjects_added'] += 1
            else:
                self.logger.info("subject already existed")
                job_results['subjects_already_exist'] += 1
        except:
            work.subjects = [subject_to_add]
            job_results['subjects_added'] += 1


    def __process_found_bestseller_edition(self, bstslr_record_isbn,
        bstslr_edition, link_struct, comment, job_results) -> None:
        if not bstslr_edition.work:
            raise Exception('No work found for the edition with isbn {}'
                            .format(bstslr_record_isbn))
        work = bstslr_edition.work
        self.__add_bestseller_review_tag(work, self.NYT_TAG_REVIEWED, job_results)
        workSaveClosure = work.save(comment)
        if self.__need_to_add_nyt_review_link(work,link_struct['url']):
            self.logger.info(
                'The NYT review link to be added '
                'for the work {} of the edition {}'
                    .format(bstslr_edition.work.olid,
                            bstslr_record_isbn))
            self.__add_link(work, link_struct)
            self.save(workSaveClosure)
            job_results['links_added'] += 1
        else:
            self.save(workSaveClosure)
            self.logger.info(
                'A NYT link already exists for the work {}'
                ' of the edition {}, skipping'
                    .format(bstslr_edition.work.olid, bstslr_record_isbn))
            job_results['links_already_exist'] += 1

    def __parse_review_record(self, review_record) -> (str, str):
        parsed_url = ''
        parsed_isbn = ''
        url_not_found = True
        if len(review_record) != 2:
            raise Exception(
                'Expected exactly 2 items in the review_record {}'.format(
                    repr(review_record)))
        for item_index, item in enumerate(review_record):
            if item.startswith(self.URL_STARTS_WITH):
                url_not_found = False
                parsed_url = review_record[item_index]
                if item_index == 0:
                    parsed_isbn = review_record[1]
                else:
                    parsed_isbn = review_record[0]
                break
        if url_not_found:
            raise Exception(
                'Expected at least one item to start with'
                ' {} in the review_record {}'
                    .format(self.URL_STARTS_WITH, repr(review_record)))
        return parsed_url, parsed_isbn

    def __process_review_record(self, review_record, comment,
        job_results) -> None:
        new_link_type = {}
        new_link_type['key'] = self.OL_LINK_TYPE_KEY_VALUE
        new_link = {}
        new_link['url'], review_record_isbn = self.__parse_review_record(
            review_record)
        new_link['title'] = self.NYT_REVIEW_DEFAULT_TITLE
        new_link['type'] = new_link_type
        try:
            bstslr_edition = self.ol.Edition.get(isbn=review_record_isbn)
            if bstslr_edition:
                self.__process_found_bestseller_edition(review_record_isbn,
                                                        bstslr_edition,
                                                        new_link, comment,
                                                        job_results)
            else:
                self.logger.info(
                    'The edition {} doesnt exist in OL, importing'
                        .format(review_record_isbn))
                self.__request_book_import_by_isbn(review_record_isbn)
                job_results['books_imported'] += 1
        except SystemExit:
            self.logger.info('Interrupted the bot while processing ISBN {}'
                             .format(review_record_isbn))
            job_results['isbns_failed'] = job_results['isbns_failed'] + 1
            self.__save_job_results(job_results)
            raise
        except:
            self.logger.exception('Failed to process ISBN {}'
                                  .format(review_record_isbn))
            job_results['isbns_failed'] = job_results['isbns_failed'] + 1

    def run(self) -> None:  # overwrites the AbstractBotJob run method
        self.dry_run = self.args.dry_run
        self.limit = None
        self.dry_run_declaration()
        job_results = {'input_file': self.args.file, 'books_imported': 0,
                       'links_added': 0, 'links_already_exist': 0,
                       'isbns_failed': 0, 'dry_run': self.dry_run
                       ,'subjects_added': 0, 'subjects_already_exist': 0}
        comment = 'Add NYT review links'
        with open(self.args.file, 'r') as fin:
            review_record_array = json.load(fin)
            for review_record in tqdm(review_record_array, unit='reviews'):
                self.__process_review_record(review_record, comment, job_results)
        self.__save_job_results(job_results)


def handler(signal_received, frame):
    msg = 'SIGINT or CTRL-C detected. Interrupting the bot'
    job.logger.info(msg)
    exit(0)


if __name__ == "__main__":
    signal(SIGINT, handler)
    job = AddNytReviewJob()

    try:
        job.run()
    except Exception as e:
        job.logger.exception("The AddNytReviewJob thrown an exception")
        raise e
