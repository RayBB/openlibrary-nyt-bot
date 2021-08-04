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
import urllib

from olclient.bots import AbstractBotJob

class AddNytBestsellerJob(AbstractBotJob):
  def need_to_add_nyt_bestseller_tag(self, work) -> bool:
    """Returns False if the book already has a tag that starts with 'nyt:'"""
    for subj in work['subjects']:
      if subj.startswith(('nyt:', 'nytimes:')):
        return False
    return True

  def add_tag(self, work, new_tag) -> None:
    """Adds a new tag to a work"""
    if 'subjects' not in work:
      work['subjects'] = list(new_tag)
    else:
      work['subjects'].append(new_tag)

  def book_exists_in_ol(self,book_isbn) -> bool:
    """Returns True if Edition with book_isbn exists. Returns False otherwise"""
    try:
      found_edition = self.ol.Edition.get(isbn=book_isbn)
      if not found_edition:
        self.logger.info('Not found edition for ISBN'+book_isbn)
        return False
      self.logger.info('Found edition for ISBN'+book_isbn)
      return True
    except Exception as e:
      #TODO check the exception type
      job.logger.exception('There is no book with ISBN ' + book_isbn)
      return False

  def request_book_import_by_isbn(self,book_isbn)-> None:
    """ Makes request to the book_isbn https://openlibrary.org/isbn/{book_isbn} """
    url = "https://openlibrary.org/isbn/%s" % (book_isbn)
    request = (urllib.Request(url, None, headers={"Referrer": "http://www.openlibrary.org"}))
    conn = urllib.urlopen(request)
    try:
      conn.read()
      job.logger.exception('Made request to ' + url)
    except Exception as e:
      self.logger.info('Failed to make request to  '+url)
    finally:
      conn.close()

  def run(self) -> None:  # overwrites the AbstractBotJob run method
    self.dry_run_declaration()

    comment = 'Add NYT bestseller tag'
    with open(self.args.file, 'r') as fin:
        bestsellers_data = json.load(fin)
        if 'error' not in bestsellers_data:
            for bestseller_group_record in bestsellers_data:
              new_tag='nyt:{'+bestseller_group_record.list_name_encoded+ \
                      '}={'+bestseller_group_record.published_date+'}'
              for bstslr_record_isbn in bestseller_group_record.isbns:
                if self.book_exists_in_ol(bstslr_record_isbn) :
                  self.logger.info('The edition '+bstslr_record_isbn+\
                                   ' exists in OL')
                  bstslr_edition = self.ol.Edition.get(isbn=bstslr_record_isbn)
                  bstslr_work = bstslr_edition.work()
                  if self.need_to_add_nyt_bestseller_tag(bstslr_work):
                      self.logger.info('The NYT tag to be added for edition '+\
                                       bstslr_record_isbn)
                      self.add_tag(bstslr_work,new_tag)
                      bstslr_work.save(comment)
                      bstslr_edition.save(comment)
                else :
                  self.logger.info('The edition '+bstslr_record_isbn+ \
                                   ' doesnt exist in OL, import requested')
                  self.request_book_import_by_isbn(bstslr_record_isbn)
if __name__ == "__main__":
  job = AddNytBestsellerJob()

  try:
    job.run()
  except Exception as e:
    job.logger.exception("")
    raise e
