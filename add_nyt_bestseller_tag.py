"""
A bot to add a NYT bestseller tag 'nyt:{list_name_encoded}={published_date}' to each book from the list of isbns.
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
$ python add_nyt_bestseller_tag.py --file=~/nyt_bstslrs.json --limit=1 --dry-run=True
NOTE: This script checks if there is a tag on a book that starts with
'nyt:' and if the book has such a tag the script does nothing.
If there is no such book with requested isbn in the OL, the script makes request
by the book isbn https://openlibrary.org/isbn/{isbn} , triggering autoimport
"""

import json

import requests
from olclient.bots import AbstractBotJob


class AddNytBestsellerJob(AbstractBotJob):
    def __init__(self):
        super().__init__(job_name='AddNytBestseller')

    def need_to_add_nyt_bestseller_tag(self, work) -> bool:
        """Returns False if the book already has
        a tag that starts with 'nyt:'"""
        try:
            for subj in work.subjects:
                if subj.startswith(('nyt:')):
                    return False
            return True
        except AttributeError:
            self.logger.exception('Failed to check subjects for work {}'
                                  .format(work.olid))
            return True

    def add_tag(self, work, new_tag) -> None:
        """Adds a new tag to a work"""
        try:
            work.subjects.append(new_tag)
            self.logger.info(
                'Successfully appended new NYT tag to work {}'.format(
                    work.olid))
        except AttributeError:
            work.subjects = [new_tag]
            self.logger.exception(
                'Failed to append subjects list for work {} but SUCCESSFULLY CREATED new subjects list with NYT tag '.format(
                    work.olid))

    def request_book_import_by_isbn(self, book_isbn) -> None:
        """ Makes request to the book_isbn
        https://openlibrary.org/isbn/{book_isbn} """
        url = 'https://openlibrary.org/isbn/{}'.format(book_isbn)
        try:
            requests.get(url)
            self.logger.info('Made request to {}'.format(url))
        except Exception as e:
            self.logger.error('Failed to make request to {}'.format(url))

    def run(self) -> None:  # overwrites the AbstractBotJob run method
        self.dry_run_declaration()

        comment = 'Add NYT bestseller tag'
        with open(self.args.file, 'r') as fin:
            bestsellers_data = json.load(fin)
            for bestseller_group_record in bestsellers_data:
                new_tag = 'nyt:{}={}'.format(
                    bestseller_group_record['list_name_encoded'],
                    bestseller_group_record['published_date'])
                for bstslr_record_isbn in bestseller_group_record['isbns']:
                    try:
                        bstslr_edition = self.ol.Edition. \
                            get(isbn=bstslr_record_isbn)
                        if bstslr_edition:
                            self.logger.info('The edition {} exists in OL'
                                             .format(bstslr_record_isbn))
                            if self.need_to_add_nyt_bestseller_tag(
                                bstslr_edition.work):
                                self.logger.info(
                                    'The NYT tag to be added for the work {} of the edition {}'
                                        .format(bstslr_edition.work.olid, bstslr_record_isbn))
                                self.add_tag(bstslr_edition.work, new_tag)
                                bstslr_edition.work.save(comment)
                                bstslr_edition.save(comment)
                            else:
                                self.logger.info('The NYT tag already exists for the work {} of the edition {}, skipping'
                                        .format(bstslr_edition.work.olid, bstslr_record_isbn))
                        else:
                            self.logger.info(
                                'The edition {} doesnt exist in OL, importing'
                                    .format(bstslr_record_isbn))
                            self.request_book_import_by_isbn(bstslr_record_isbn)
                    except:
                        self.logger.exception('Failed to process ISBN {}'
                                              .format(bstslr_record_isbn))


if __name__ == "__main__":
    job = AddNytBestsellerJob()

    try:
        job.run()
    except Exception as e:
        job.logger.exception("The AddNytBestsellerJob thrown an exception")
        raise e
