"""
A bot to add a NYT review link to the links array for a work
 {'title': '"It\'s a steal" (NYT review)',
   'url': 'https://www.nyt.com/books/2007/jan/06/featuresreviews',
   'type': {'key': '/type/link'}}
 each book from the list of ISBNs.

The list of reviews to add is a json file of the following format:
[
    {
    },
]
This script would be called from the command line like so:
$ python add_nyt_review.py --file=~/nyt_reviews.json --dry-run=True
NOTE: This script checks if there is a link in the links with the same URL
If there is no such book with requested isbn in the OL, the script makes request
by the book isbn https://openlibrary.org/isbn/{isbn} , triggering auto import
"""

import json

import requests
from olclient.bots import AbstractBotJob


class AddNytReviewJob(AbstractBotJob):

    def __init__(self):
        super().__init__(job_name='AddNytReviewJob')

    def need_to_add_nyt_review_link(self, work, link) -> bool:
        """Returns False if the book already has
        the same link in the links section"""
        try:
            for lnk in work.links:
                if lnk.url.startswith(link):
                    return False
            return True
        except AttributeError:
            self.logger.info(
                'Failed to check link for work {}, no links list exist'
                .format(work.olid))
            return True

    def add_link(self, work, link_struct) -> None:
        """Adds a new link to a work"""
        try:
            work.links.extend(link_struct)
            self.logger.info(
                'Successfully extended new link with NYT rewiew to work {}'
                    .format(work.olid))
        except AttributeError:
            work.subjects = [link_struct]
            self.logger.info(
                'Failed to append links list for work {} but '
                'SUCCESSFULLY CREATED new links list with NYT review'
                    .format(work.olid))

    def request_book_import_by_isbn(self, book_isbn) -> None:
        """ Makes request to the book_isbn
        https://openlibrary.org/isbn/{book_isbn} """
        url = 'https://openlibrary.org/isbn/{}'.format(book_isbn)
        try:
            if not self.dry_run:
                requests.get(url)
            self.logger.info('Made request to {}'.format(url))
        except Exception as e:
            self.logger.error('Failed to make request to {}'.format(url))

    def save_job_results(self, job_results) -> None:
        self.logger.info('Job execution results: {}'.format(repr(job_results)))
        with open('add_nyt_review_result.json', 'w', encoding='utf-8') as f:
            json.dump(job_results, f, ensure_ascii=False, indent=4)

    def process_found_bestseller_edition(self, bstslr_record_isbn,
        bstslr_edition, link_struct, comment, job_results) -> None:
        if self.need_to_add_nyt_review_link(bstslr_edition.work):
            self.logger.info(
                'The NYT review link to be added '
                'for the work {} of the edition {}'
                    .format(bstslr_edition.work.olid,
                            bstslr_record_isbn))
            self.add_link(bstslr_edition.work, link_struct)
            bstslr_edition.work.save(comment)
            bstslr_edition.save(comment)
            job_results['links_added'] = job_results['links_added'] + 1
        else:
            self.logger.info(
                'A NYT link already exists for the work {}'
                ' of the edition {}, skipping'
                    .format(bstslr_edition.work.olid, bstslr_record_isbn))
            job_results['links_already_exist'] = \
                job_results['links_already_exist'] + 1

    def process_bestseller_group_record(self, bestseller_group_record, comment,
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
                    self.process_found_bestseller_edition(bstslr_record_isbn,
                                                          bstslr_edition,
                                                          new_tags, comment,
                                                          job_results)
                else:
                    self.logger.info(
                        'The edition {} doesnt exist in OL, importing'
                            .format(bstslr_record_isbn))
                    self.request_book_import_by_isbn(bstslr_record_isbn)
                    job_results['books_imported'] = job_results[
                                                        'books_imported'] + 1
            except:
                self.logger.exception('Failed to process ISBN {}'
                                      .format(bstslr_record_isbn))
                job_results['isbns_failed'] = job_results['isbns_failed'] + 1

    def run(self) -> None:  # overwrites the AbstractBotJob run method
        self.dry_run_declaration()
        job_results = {'input_file': self.args.file, 'books_imported': 0,
                       'links_added': 0, 'links_already_exist': 0,
                       'isbns_failed': 0, 'dry_run': self.dry_run}
        comment = 'Add NYT review links'
        with open(self.args.file, 'r') as fin:
            bestsellers_data = json.load(fin)
            for bestseller_group_record in bestsellers_data:
                self.process_bestseller_group_record(bestseller_group_record,
                                                     comment, job_results)
        self.save_job_results(job_results)


if __name__ == "__main__":
    job = AddNytReviewJob()

    try:
        job.run()
    except Exception as e:
        job.logger.exception("The AddNytReviewJob thrown an exception")
        raise e
