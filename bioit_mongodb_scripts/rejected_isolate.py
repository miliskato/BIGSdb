import logging
import sys
from typing import Tuple

from bioit_bigsdb_scripts.components.psql.psql_tbl_rejected_isolates import TblRejectedIsolates
from bioit_bigsdb_scripts.utils.url_helper import UrlHelper
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


class RejectedIsolate:
    """
    Class to insert a rejected isolate in BIGSdb.
    """

    def __init__(self, species: str, pseudo_id: str) -> None:
        """
        Initializes this class.
        :param species: Commonly used bioit species name: either genus or specific like stec
        :param pseudo_id: The pseudo id of a sample
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

        self._species = species
        self._pseudo_id = pseudo_id
        self._mongo_config_data = get_mongodb_config_data()

        # Open collection Atlas MongoDB
        self._mongoinit = MongoInitialisation(
            self._species,
            mongo_config_data=self._mongo_config_data,
            selected_connection_string='CONNECTION_STRING_AZURE'
        )
        self._rejected_isolates_collection = self._mongoinit.initialise_isolates_rejected_coreqc_collection()

        # Open collection local MongoDB
        self._mongoinit_local = MongoInitialisation(
            self._species,
            mongo_config_data=self._mongo_config_data,
            selected_connection_string='CONNECTION_STRING_LOCAL'
        )
        self._mappingtable_collection = self._mongoinit_local.initialise_mapping_table_collection()

        # Open BIGSdb rejected_isolates table
        self._rejected_isolates_psql_tbl = TblRejectedIsolates(self._species)

        self._isolate = self._get_isolate_id()
        self._rejected_isolate_document = self._get_rejected_isolate_document()

    def _get_isolate_id(self) -> str:
        """
        Returns the sample id of the rejected isolate.
        :return: The sample id
        """
        sample_id = str(self._mappingtable_collection.find_one({'pseudo_id': self._pseudo_id})['_id'])
        return sample_id

    def _get_rejected_isolate_document(self) -> dict:
        """
        Returns the MongoDB document of the rejected isolate.
        :return: MongoDB rejected isolate document (dictionary)
        """
        document = self._rejected_isolates_collection.find_one({'_id': self._pseudo_id})
        return document

    def insert_in_rejected_isolates_table(self) -> None:
        """
        Inserts the rejected isolate into the rejected isolates table in BIGSdb.
        :return: None
        """
        insertion_date, insertion_type, rejection_reasons, report_link = self._retrieve_fields()
        isolate_exists = self._rejected_isolates_psql_tbl.exists_isolate((self._isolate,))
        if isolate_exists[0][0]:
            self._rejected_isolates_psql_tbl.delete_isolate((self._isolate,))
        self._rejected_isolates_psql_tbl.insert_isolate(
            (self._isolate, insertion_date, rejection_reasons, insertion_type, report_link))
        self._update_mongodb()

    def _retrieve_fields(self) -> Tuple[str, str, str, str]:
        """
        Retrieves the necessary fields from the rejected isolate document to insert in BIGSdb.
        :return: insertion date, insertion type, rejection reasons and report link
        """
        insertion_date = str(self._rejected_isolate_document['creation_date'])
        insertion_type = str(self._rejected_isolate_document['insertion_type'])
        if insertion_type == 'manual':
            rejection_reasons = self._rejected_isolate_document['rejection_reasons']['manual']
            report_link = 'unavailable'
        else:
            rejection_reasons = ', '.join(
                qc_metric['reason'] for qc_metric in self._rejected_isolate_document['rejection_reasons'].values())
            rejected_isolate_id = str(self._rejected_isolates_psql_tbl.select_last_rejected_isolate_id() + 1)
            report_url = UrlHelper.report_for_validation_rejected_isolate_id(
                self._species, self._pseudo_id, rejected_isolate_id, insertion_date, 'rejected_isolate')
            report_link = f'<a href="{report_url}" target = "_blank"> report </a>'
        return insertion_date, insertion_type, rejection_reasons, report_link

    def _update_mongodb(self) -> None:
        """
        Inserts an extra field inserted_in_bigsdb in MongoDB for the rejected isolate.
        :return: None
        """
        self._rejected_isolates_collection.update_one({'_id': self._pseudo_id}, {'$set': {'inserted_in_bigsdb': True}})
