import datetime
import socket
import sys
from pathlib import Path
from typing import Any, Dict, List

from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSubmissions, TblIsolateSubmissionIsolates, \
    TblIsolateSubmissionFieldOrder
from bioit_bigsdb_scripts.utils.url_helper import UrlHelper
from bioit_mongodb_scripts.model.json_model import MongoRecordDict
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation


def _insert_submission_bigs(sample_docs: List[MongoRecordDict], validation_type: str, species: str, mongo_config_data: Dict[str, Any]) -> None:
    """
    Inserts a given list of submissions into bigsdb
    :param sample_docs: list of documents to be submitted
    :param validation_type: either bad_quality or resequencing
    :param species: commonly used bioit species name: either genus or specific like stec
    :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
    :return: None
    """
    mongoinit_local = MongoInitialisation(species, mongo_config_data=mongo_config_data,
                                          selected_connection_string='CONNECTION_STRING_LOCAL')
    mappingtable_collection = mongoinit_local.initialise_mapping_table_collection()

    with TblSubmissions(species) as isolates_sub_psql_tbl, \
            TblIsolateSubmissionIsolates(species) as isolates_isosubiso_psql_tbl, \
            TblIsolateSubmissionFieldOrder(species) as isolates_isosubfo_psql_tbl:
    #        TblMappingTable(species) as isolates_mapping_psql_tbl:
        for mongo_record in sample_docs:
            isolate_id = mappingtable_collection.find_one({'pseudo_id': mongo_record['_id']})['_id']
            isolates_sub_psql_tbl.insert_submission((validation_type,))
            pipeline_hash = mongo_record['results']['pipeline_hash']
            report_url = UrlHelper.report_for_validation(species, mongo_record['_id'], mongo_record['latest_analysis_date'], validation_type)
            report_link = f'<a href="{report_url}" target = "_blank" class="small_submit"> Get report preview </a>'

            isolates_isosubiso_psql_tbl.insert_validation_metadata(('html_report', report_link))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('isolate_id', isolate_id))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('validation_type', validation_type))
            # The indexes below are necessary, if they are not inserted the values above are not visible
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('html_report', 1))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('isolate_id', 2))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('validation_type', 3))


def samples_to_validation_bigs(species: str, mongo_config_data: Dict[str, Any] = None) -> None:
    """
    Send samples in the badqc_sample and resequencing collection to be validated on BIGSdb
    :param species: commonly used bioit species name: either genus or specific like stec
    :param mongo_config_data: Pass provided mongo_config_data to MongoInitialisation,
    else get mongo_config_data from file in mongoinit
    :return: None
    """
    mongo_config_data = mongo_config_data
    # Open collections
    mongoinit = MongoInitialisation(species, mongo_config_data=mongo_config_data, selected_connection_string='CONNECTION_STRING_AZURE')
    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
        isolates_resequencing_collection = mongoinit.initialise_collections()

    # fetch all documents in the bad samples of the species
    update_collection = mongoinit.initialise_update_collection()
    query = update_collection.find_one({'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname()})
    last_run_date = query['last_update_date'] if query else datetime.datetime(1970, 1, 1)  # unix time
    current_date = datetime.datetime.now(datetime.timezone.utc)
    bad_samples = list(map(lambda x: MongoRecordDict(x),isolates_badqc_collection.find({'submission_status': 'pending_for_submission'})))
    _insert_submission_bigs(bad_samples, 'bad_quality', species, mongo_config_data)
    for isolate in bad_samples:
        doc_id=isolate.get_id()
        isolates_badqc_collection.update_one({'_id': doc_id},
                                                {'$set': {'submission_status': 'submitted_in_bigsdb'}},
                                                upsert=True)
    # resequencing_samples = list(map(lambda x: MongoRecordDict(x),isolates_resequencing_collection.find({'submission_status': 'pending_for_submission'})))
    # _insert_submission_bigs(resequencing_samples, 'resequencing', species, mongo_config_data)
    #for isolate in resequencing_samples:
    #    doc_id=isolate.get_id()
    #    isolates_resequencing_collection.update_one({'_id': doc_id},
    #                                            {'$set': {'submission_status': 'submitted_in_bigsdb'}},
    #                                            upsert=True)
    # update last date of update
    if query:
        update_collection.with_options(write_concern=WriteConcern(w="majority")).find_one_and_update(
            {'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname()}, {'$set': {'last_update_date': current_date}})
    else:
        update_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
            {'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname(), 'last_update_date': last_run_date})
