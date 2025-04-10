import datetime
import socket
import sys
from pathlib import Path
from typing import Any, Dict, Literal

from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSubmissions, TblIsolateSubmissionIsolates, \
    TblIsolateSubmissionFieldOrder
from bioit_bigsdb_scripts.utils.url_helper import UrlHelper
from bioit_mongodb_scripts.model.json_model import MongoRecordDict
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation


class SampleToValidationBigs:
    """
    Pushes isolates from MongoDB badqc/resequencing collections into BIGSdb's submission system if it's not already done
    """

    def __init__(self, species: str, isolate_id: str, mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Call methods to insert samples into BIGSdb submission table
        :param species: commonly used bioit species name: either genus or specific like stec
        :param isolate_id: name of the isolate
        :param mongo_config_data: mongo_config_data for MongoInitialisation
        :return: None
        """
        self.mongo_config_data = mongo_config_data
        self.species = species
        self.isolate_id = isolate_id

        self._submission_into_bigs('bad_quality')
        # self._submission_into_bigs('resequencing')

    def _submission_into_bigs(self, sample_type: Literal['bad_quality', 'resequencing']) -> None:
        """
        Select samples pending for submission from either badqc or resequencing collection and launches their submission in BIGSdb
        :param: sample_type: str that should be either "bad_quality" or "resequencing"
        :return: None
        """
        mongoinit = MongoInitialisation(self.species, mongo_config_data=self.mongo_config_data,
                                        selected_connection_string='CONNECTION_STRING_AZURE')
        _, _, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
        update_collection = mongoinit.initialise_update_collection()

        mongo_collection = isolates_badqc_collection if sample_type == 'bad_quality' else isolates_resequencing_collection

        isolate_to_submit = MongoRecordDict(mongo_collection.find_one({"_id": self.isolate_id}))
        current_date = datetime.datetime.now(datetime.timezone.utc)
        self.__insert_submission_bigs(isolate_to_submit, sample_type)
        for isolate in isolate_to_submit:
            doc_id = isolate.get_id()
            mongo_collection.update_one({'_id': doc_id},
                                        {'$set': {'submission_status': 'submitted_in_bigsdb'}})
        if current_date:
            update_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                {'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname()},
                {'$set': {'last_update_date': current_date}}, upsert=True)

    def __insert_submission_bigs(self, sample_doc: MongoRecordDict, validation_type: str) -> None:
        """
        Inserts a given list of submissions into bigsdb
        :param sample_doc: mongo db document of the isolate
        :param validation_type: either bad_quality or resequencing
        :return: None
        """
        mongoinit_local = MongoInitialisation(self.species, mongo_config_data=self.mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_LOCAL')
        mappingtable_collection = mongoinit_local.initialise_mapping_table_collection()

        with TblSubmissions(self.species) as isolates_sub_psql_tbl, \
                TblIsolateSubmissionIsolates(self.species) as isolates_isosubiso_psql_tbl, \
                TblIsolateSubmissionFieldOrder(self.species) as isolates_isosubfo_psql_tbl:

            isolate_id = mappingtable_collection.find_one({'pseudo_id': sample_doc['_id']})['_id']
            isolates_sub_psql_tbl.insert_submission((validation_type,))
            report_url = UrlHelper.report_for_validation(self.species, sample_doc['_id'],
                                                         sample_doc['latest_analysis_date'], validation_type)
            report_link = f'<a href="{report_url}" target = "_blank" class="small_submit"> Get report preview </a>'

            isolates_isosubiso_psql_tbl.insert_validation_metadata(('html_report', report_link))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('isolate_id', isolate_id))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('validation_type', validation_type))
            # The indexes below are necessary, if they are not inserted the values above are not visible
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('html_report', 1))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('isolate_id', 2))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('validation_type', 3))
