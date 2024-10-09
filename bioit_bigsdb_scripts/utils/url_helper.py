import urllib.parse

class UrlHelper:
    """Url encoder to facilitate the construction of url in the BIGSdb environment"""
    BASE_URL: str = '/cgi-bin/bigsdb/bigsdb.pl?'
    SCIENSANO_PAGE: str = 'sciensanoReport'

    @staticmethod
    def _create(page: str, specie: str, query: dict[str, str], anchor: str = None):
        """add the page and db attribute to the base url and an anchor if provided"""
        query['page'] = page
        query['db'] = f"bigsdb_{specie}_isolates"

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
    def report_for_validation(specie: str, pseudo_id: str, submit_date: str, validation_type: str, getzip: bool = False) -> str:
        """
        encodes url to get the report waiting for validation
        :param specie: species of interest
        :param pseudo_id: pseudo id found in MongoDB
        :param submit_date: last analysis date in MongoDB
        :param validation_type: type of validation based on info from submission
        :return: url used to get the report for the submitted isolate
        """
        query = {
            'pseudo_id': pseudo_id,
            'submit_date': submit_date,
            'validation_type': validation_type,
            'getzip': 'yes' if getzip else 'no'
        }
        return UrlHelper._create(UrlHelper.SCIENSANO_PAGE, specie, query)