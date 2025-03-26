import urllib.parse
from typing import Dict


class UrlHelper:
    """Url encoder to facilitate the construction of url in the BIGSdb environment"""
    BASE_URL: str = '/cgi-bin/bigsdb/bigsdb.pl?'
    SCIENSANO_PAGE: str = 'sciensanoReport'

    @staticmethod
    def _create(page: str, species: str, query: Dict[str, str], anchor: str = None) -> str:
        """
        add the page and db attribute to the base url and an anchor if provided
        :param page: name of the page to call in the url
        :param species: name of the species of interest
        :param query: dictionary hosting key-value pairs used by the url builder
        :return: returns the url
        """
        query['page'] = page
        query['db'] = f"bigsdb_{species}_isolates"

        return UrlHelper.BASE_URL + urllib.parse.urlencode(query) + (f"#{anchor}" if anchor is not None else '')

    @staticmethod
    def report_for_isolate(species: str, isolate_id: str, anchor: str = None) -> str:
        """
        encodes url to get the report of an isolate already present in BIGSdb
        :param species: species of interest
        :param isolate_id: id of isolate
        :param anchor: anchor url to target subsection of the report
        :return: the url used to get the report
        """
        query = {'id': isolate_id, 'getzip': 'no'}
        return UrlHelper._create(UrlHelper.SCIENSANO_PAGE, species, query, anchor)

    @staticmethod
    def report_for_validation(species: str, pseudo_id: str, submit_date: str, validation_type: str, getzip: bool = False) -> str:
        """
        encodes url to get the report waiting for validation
        :param species: species of interest
        :param pseudo_id: pseudo id found in MongoDB
        :param submit_date: last analysis date in MongoDB
        :param validation_type: type of validation based on info from submission
        :param getzip: if "False" (default), only html report is provided and if "True", zip archive is created
        :return: url used to get the report for the submitted isolate
        """
        query = {
            'pseudo_id': pseudo_id,
            'submit_date': submit_date,
            'validation_type': validation_type,
            'getzip': 'yes' if getzip else 'no'
        }
        return UrlHelper._create(UrlHelper.SCIENSANO_PAGE, species, query)

    @staticmethod
    def report_for_validation_rejected_isolate_id(species: str, pseudo_id: str, rejected_isolate_id: str, submit_date: str, validation_type: str, getzip: bool = False) -> str:
        """
        encodes url to get the report waiting for validation
        :param species: species of interest
        :param pseudo_id: pseudo id found in MongoDB
        :param rejected_isolate_id: id of the rejected isolate
        :param submit_date: creation date in MongoDB
        :param validation_type: type of validation based on info from submission
        :param getzip: if "False" (default), only html report is provided and if "True", zip archive is created
        :return: url used to get the report for the submitted isolate
        """
        query = {
            'pseudo_id': pseudo_id,
            'rejected_isolate_id': rejected_isolate_id,
            'submit_date': submit_date,
            'validation_type': validation_type,
            'getzip': 'yes' if getzip else 'no'
        }
        return UrlHelper._create(UrlHelper.SCIENSANO_PAGE, species, query)
