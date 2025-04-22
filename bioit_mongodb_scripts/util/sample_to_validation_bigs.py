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
    Pushes isolates from MongoDB goodqc/badqc/resequencing collections into BIGSdb's submission system if it's not
    already done.
    """

    def __init__(self, species: str, isolate_id: str, pseudo_id: str, sample_type: Literal['good_quality', 'bad_quality', 'resequencing'],  mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Call methods to insert samples into BIGSdb submission table.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param isolate_id: name of the isolate
        :param pseudo_id: Pseudo ID
        :param sample_type: str that should be either "good_quality", "bad_quality" or "resequencing"
        :param mongo_config_data: mongo_config_data for MongoInitialisation
        :return: None
        """
        self._mongo_config_data = mongo_config_data
        self._species = species
        self._isolate_id = isolate_id
        self._pseudo_id = pseudo_id
        self._sample_type = sample_type
        self._submission_into_bigs()

    def _submission_into_bigs(self) -> None:
        """
        Select samples pending for submission from either the goodqc, badqc or resequencing collection and launches
        their submission in BIGSdb.
        :return: None
        """
        mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                        selected_connection_string='CONNECTION_STRING_AZURE')
        _, _, isolates_badqc_collection, isolates_resequencing_collection, isolates_goodqc_collection = mongoinit.initialise_collections()
        update_collection = mongoinit.initialise_update_collection()

        mongo_collection = isolates_badqc_collection if self._sample_type == 'bad_quality' else \
            isolates_resequencing_collection if self._sample_type == 'resequencing' else isolates_goodqc_collection

        isolate_to_submit = MongoRecordDict(mongo_collection.find_one({"_id": self._pseudo_id}))
        current_date = datetime.datetime.now(datetime.timezone.utc)
        self.__insert_submission_bigs(isolate_to_submit)
        mongo_collection.update_one({'_id': self._pseudo_id},
                                    {'$set': {'submission_status': 'submitted_in_bigsdb'}})
        if current_date:
            update_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                {'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname()},
                {'$set': {'last_update_date': current_date}}, upsert=True)

    def __insert_submission_bigs(self, sample_doc: MongoRecordDict) -> None:
        """
        Inserts a given isolate in the submission system of bigsdb
        :param sample_doc: mongo db document of the isolate
        :return: None
        """
        with TblSubmissions(self._species) as isolates_sub_psql_tbl, \
                TblIsolateSubmissionIsolates(self._species) as isolates_isosubiso_psql_tbl, \
                TblIsolateSubmissionFieldOrder(self._species) as isolates_isosubfo_psql_tbl:

            isolates_sub_psql_tbl.insert_submission((self._sample_type,))
            report_url = UrlHelper.report_for_validation(self._species, sample_doc['_id'],
                                                         sample_doc['latest_analysis_date'], self._sample_type)
            report_link = f'<a href="{report_url}" target = "_blank"> report </a>'

            isolates_isosubiso_psql_tbl.insert_validation_metadata(('html_report', report_link))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('isolate_id', self._isolate_id))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('validation_type', self._sample_type))
            # The indexes below are necessary, if they are not inserted the values above are not visible
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('html_report', 1))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('isolate_id', 2))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('validation_type', 3))
