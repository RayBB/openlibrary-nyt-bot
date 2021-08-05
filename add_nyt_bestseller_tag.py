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

import requests
from olclient.bots import AbstractBotJob


class AddNytBestsellerJob(AbstractBotJob):
    NYT_TAG_PREFIX = 'nyt:'
    NYT_TAG_BESTSELLER = 'New York Times bestseller'
    OL_IMPORT_URL_TEMPLATE = 'https://openlibrary.org/isbn/{}'

    def __init__(self):
        super().__init__(job_name='AddNytBestseller')

    def __need_to_add_nyt_bestseller_tag(self, work) -> bool:
        """Returns False if the book already has
        a tag that starts with 'nyt:'"""
        try:
            for subj in work.subjects:
                if subj.startswith((self.NYT_TAG_PREFIX,
                                    self.NYT_TAG_BESTSELLER)):
                    return False
            return True
        except AttributeError:
            self.logger.info(
                'Failed to check subjects for work {}, no subject list exist'
                    .format(work.olid))
            return True

    def __add_tags(self, work, new_tags) -> None:
        """Adds a new tag to a work"""
        try:
            work.subjects.extend(new_tags)
            self.logger.info(
                'Successfully extended new NYT tags to work {}'.format(
                    work.olid))
        except AttributeError:
            work.subjects = new_tags
            self.logger.info(
                'Failed to append subjects list for work {} but '
                'SUCCESSFULLY CREATED new subjects list with NYT tags'.format(
                    work.olid))

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
        with open('add_nyt_bestseller_result.json', 'w', encoding='utf-8') as f:
            json.dump(job_results, f, ensure_ascii=False, indent=4)

    def __process_found_bestseller_edition(self, bstslr_record_isbn,
        bstslr_edition, new_tags, comment, job_results) -> None:
        if not bstslr_edition.work:
            raise Exception('No work found for the edition with isbn {}'
                            .format(bstslr_record_isbn))
        if self.__need_to_add_nyt_bestseller_tag(bstslr_edition.work):
            self.logger.info(
                'The NYT tags to be added for the work {} of the edition {}'
                    .format(bstslr_edition.work.olid,
                            bstslr_record_isbn))
            self.__add_tags(bstslr_edition.work, new_tags)
            bstslr_edition.work.save(comment)
            bstslr_edition.save(comment)
            job_results['tags_added'] = job_results['tags_added'] + 1
        else:
            self.logger.info(
                'A NYT tag already exists for the work {}'
                ' of the edition {}, skipping'
                    .format(bstslr_edition.work.olid, bstslr_record_isbn))
            job_results['tags_already_exist'] = \
                job_results['tags_already_exist'] + 1

    def __process_bestseller_group_record(self, bestseller_group_record,
        comment,
        job_results) -> None:
        new_tags = ['{}{}={}'.format(
            self.NYT_TAG_PREFIX,
            bestseller_group_record['list_name_encoded'],
            bestseller_group_record['published_date']),
            self.NYT_TAG_BESTSELLER]
        for bstslr_record_isbn in bestseller_group_record['isbns']:
            try:
                bstslr_edition = self.ol.Edition.get(
                    isbn=bstslr_record_isbn)
                if bstslr_edition:
                    self.__process_found_bestseller_edition(bstslr_record_isbn,
                                                            bstslr_edition,
                                                            new_tags, comment,
                                                            job_results)
                else:
                    self.logger.info(
                        'The edition {} doesnt exist in OL, importing'
                            .format(bstslr_record_isbn))
                    self.__request_book_import_by_isbn(bstslr_record_isbn)
                    job_results['books_imported'] = job_results[
                                                        'books_imported'] + 1
            except:
                self.logger.exception('Failed to process ISBN {}'
                                      .format(bstslr_record_isbn))
                job_results['isbns_failed'] = job_results['isbns_failed'] + 1

    def run(self) -> None:  # overwrites the AbstractBotJob run method
        self.dry_run_declaration()
        job_results = {'input_file': self.args.file, 'books_imported': 0,
                       'tags_added': 0, 'tags_already_exist': 0,
                       'isbns_failed': 0, 'dry_run': self.dry_run}
        comment = 'Add NYT bestseller tag'
        with open(self.args.file, 'r') as fin:
            bestsellers_data = json.load(fin)
            for bestseller_group_record in bestsellers_data:
                self.__process_bestseller_group_record(bestseller_group_record,
                                                       comment, job_results)
        self.__save_job_results(job_results)


if __name__ == "__main__":
    job = AddNytBestsellerJob()

    try:
        job.run()
    except Exception as e:
        job.logger.exception("The AddNytBestsellerJob thrown an exception")
        raise e
