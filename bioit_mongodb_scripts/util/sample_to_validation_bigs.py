import datetime
import socket
import sys
from pathlib import Path
from typing import Literal, Tuple, Union

from pymongo.write_concern import WriteConcern
from pymongo.collection import Collection

from bioit_bigsdb_scripts.utils.literal_helper import validate_literal

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSubmissions, TblIsolateSubmissionIsolates, \
    TblIsolateSubmissionFieldOrder
from bioit_bigsdb_scripts.utils.url_helper import UrlHelper
from bioit_mongodb_scripts.model.json_model import MongoRecordDict
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation

QualityLiteral = Literal['warning', 'good']
QualityValues = Union[QualityLiteral, str]

ResequencingLiteral = Literal['yes', 'no']
ResequencingValues = Union[ResequencingLiteral, str]


class SampleToValidationBigs:
    """
    Pushes isolates from MongoDB goodqc/warningqc/resequencing collections into BIGSdb's submission system if it's not
    already done.
    """

    def __init__(self, species: str, isolate_id: str, pseudo_id: str, quality: QualityValues,
                 resequencing: ResequencingValues, mongo_config_provider: MongoConfigProvider) -> None:
        """
        Call methods to insert samples into BIGSdb submission table.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param isolate_id: name of the isolate
        :param pseudo_id: Pseudo ID
        :param quality: str, either "warning" or "good"
        :param resequencing: str, either yes or no
        :param mongo_config_provider: the mongodb configuration provider
        :return: None
        """
        self._mongo_config_provider = mongo_config_provider
        self._species = species
        self._isolate_id = isolate_id
        self._pseudo_id = pseudo_id
        self._quality = quality
        self._resequencing = resequencing
        self._collection, self._update_collection, self._validation_type = self._get_collections_and_validation_type()
        validate_literal(quality, QualityLiteral)
        validate_literal(resequencing, ResequencingLiteral)

    def _get_collections_and_validation_type(self) -> Tuple[Collection, Collection, str]:
        """
        Returns the MongoDB collection, MongoDB update collection and the validation type.
        :return: the MongoDB collection, MongoDB update collection and validation type
        """
        mongoinit = MongoInitialisation(self._species, self._mongo_config_provider.get_azure_connection_string(self._species), self._mongo_config_provider.dtap)
        _, _, isolates_warningqc_collection, isolates_resequencing_collection, isolates_goodqc_collection = \
            mongoinit.initialise_collections()
        update_collection = mongoinit.initialise_update_collection()

        if self._resequencing == 'yes':
            collection = isolates_resequencing_collection
            validation_type = 'resequencing'
        elif self._quality == 'good':
            collection = isolates_goodqc_collection
            validation_type = 'good_quality'
        else:
            collection = isolates_warningqc_collection
            validation_type = 'warning_quality'
        return collection, update_collection, validation_type

    def submission_into_bigs(self) -> None:
        """
        Select samples pending for submission from either the goodqc, warningqc or resequencing collection and launches
        their submission in BIGSdb.
        :return: None
        """
        isolate_to_submit = MongoRecordDict(self._collection.find_one({"_id": self._pseudo_id}))
        current_date = datetime.datetime.now(datetime.timezone.utc)
        self._insert_submission_bigs(isolate_to_submit)
        self._collection.update_one({'_id': self._pseudo_id},
                                    {'$set': {'submission_status': 'submitted_in_bigsdb'}})
        if current_date:
            self._update_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                {'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname()},
                {'$set': {'last_update_date': current_date}}, upsert=True)

    def _insert_submission_bigs(self, sample_doc: MongoRecordDict) -> None:
        """
        Inserts a given isolate in the submission system of bigsdb
        :param sample_doc: mongo db document of the isolate
        :return: None
        """
        with TblSubmissions(self._species) as isolates_sub_psql_tbl, \
                TblIsolateSubmissionIsolates(self._species) as isolates_isosubiso_psql_tbl, \
                TblIsolateSubmissionFieldOrder(self._species) as isolates_isosubfo_psql_tbl:
            warning_reasons = self.__get_warning_reasons(sample_doc)
            isolates_sub_psql_tbl.insert_submission((self._quality, self._resequencing, warning_reasons))
            report_url = UrlHelper.report_for_validation(self._species, sample_doc['_id'],
                                                         sample_doc['latest_analysis_date'],
                                                         self._validation_type)
            report_link = f'<a href="{report_url}" target = "_blank"> report </a>'

            isolates_isosubiso_psql_tbl.insert_validation_metadata(('html_report', report_link))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('isolate_id', self._isolate_id))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('validation_type', self._validation_type))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('quality', self._quality))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('resequencing', self._resequencing))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('warning_reasons', warning_reasons))
            # The indexes below are necessary, if they are not inserted the values above are not visible
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('html_report', 1))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('isolate_id', 2))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('validation_type', 3))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('quality', 4))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('resequencing', 5))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('warning_reasons', 6))

    @staticmethod
    def __get_warning_reasons(sample_doc: MongoRecordDict) -> str:
        """
        Returns the warning reasons of a sample.
        :param sample_doc: mongo db document of the isolate
        :return: str, warning reasons
        """
        warning_reasons = 'NA'
        if sample_doc.get('warning_reasons'):
            warning_reasons = ', '.join(
                qc_metric['reason'] for qc_metric in sample_doc['rejection_reasons'].values())
        return warning_reasons
