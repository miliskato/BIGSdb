import datetime
import sys
import socket
from pathlib import Path
from typing import Any, Dict, List

from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_bigsdb_scripts.components.psql import TblSubmissions, TblIsolateSubmissionIsolates, \
    TblIsolateSubmissionFieldOrder


def _insert_submission_bigs(sample_docs: List[Dict[str, Any]], validation_type: str, species: str) -> None:
    """
    Inserts a given list of submissions into bigsdb
    :param sample_docs: list of documents to be submitted
    :param validation_type: either bad_quality or resequencing
    :param species: commonly used bioit species name: either genus or specific like stec
    :return: None
    """
    with TblSubmissions(species) as isolates_sub_psql_tbl, \
            TblIsolateSubmissionIsolates(species) as isolates_isosubiso_psql_tbl, \
            TblIsolateSubmissionFieldOrder(species) as isolates_isosubfo_psql_tbl:
        for doc in sample_docs:
            isolates_sub_psql_tbl.insert_submission((validation_type,))
            html_path = doc['report_directory']
            html_link = f'<p><a href="{html_path}" target="_blank"> html report</a></p>'
            # end of dev code
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('html_report', html_link))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('isolate_id', doc['_id']))
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
    # Open collections
    mongoinit = MongoInitialisation(species, mongo_config_data=mongo_config_data)
    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
        isolates_resequencing_collection = mongoinit.initialise_collections()

    # fetch all documents in the bad samples of the species
    update_collection = mongoinit.initialise_update_collection()
    query = update_collection.find_one({'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname()})
    last_run_date = query['last_update_date'] if query else datetime.datetime(1970, 1, 1)  # unix time
    current_date = datetime.datetime.utcnow()
    bad_samples = list(isolates_badqc_collection.find({'creation_date': {'$gt': last_run_date}}))
    _insert_submission_bigs(bad_samples, 'bad_quality', species)
    resequencing_samples = list(isolates_resequencing_collection.find({'creation_date': {'$gt': last_run_date}}))
    _insert_submission_bigs(resequencing_samples, 'resequencing', species)
    # update last date of update
    if query:
        update_collection.with_options(write_concern=WriteConcern(w="majority")).find_one_and_update(
            {'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname()}, {'$set': {'last_update_date': current_date}})
    else:
        update_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
            {'metadata': 'last_validation_to_bigs_update', 'host': socket.gethostname(), 'last_update_date': last_run_date})
