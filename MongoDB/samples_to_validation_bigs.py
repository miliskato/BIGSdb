import datetime
import logging
import os
import smtplib
import socket
import sys
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List

import pymongo
import yaml
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from MongoDB.util.mongo_initialisation import MongoInitialisation
from MongoDB.config import MONGO_CONFIG
from bioit_custom_scripts.components.psql_tables_queries import TblSubmissions, TblIsolateSubmissionIsolates, TblIsolateSubmissionFieldOrder
from bioit_custom_scripts.components.python_utility_functions import get_bigsdb_config_data

def send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)
    logging.info(content)

def _insert_submission_bigs(sample_docs: List[Dict[str, Any]], validation_type: str, species: str) -> None:
    """
    Inserts a given list of submissions into bigsdb
    :param sample_docs: list of documents to be submitted
    :param validation_type: either bad_quality or resequencing
    :param species: commonly used bioit species name: either genus or specific like stec
    :return:
    """
    with TblSubmissions(species) as isolates_sub_psql_tbl, \
        TblIsolateSubmissionIsolates(species) as isolates_isosubiso_psql_tbl, \
        TblIsolateSubmissionFieldOrder(species) as isolates_isosubfo_psql_tbl:
        for doc in sample_docs:
            isolates_sub_psql_tbl.insert_submission((validation_type,))
            # todo need to set a proper method to build links based on the sample to transfer
            # for testing purposes
            html_path = 'http://bioit-bigs-dev.sciensano.be/galaxyreports/listeria/110-001_S68_L001/report.html'
            # dev code, not set yet
            html_path = str(html_path).replace('/reports/', '/galaxyreports/')
            html_link = f'<p><a href="{html_path}" target="_blank"> html report</a></p>'
            # end of dev code
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('html_report', html_link))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('isolate_id', doc['_id']))
            isolates_isosubiso_psql_tbl.insert_validation_metadata(('validation_type', validation_type))
            # todo i wonder if these indexes always need to be inserted? it seems like a lot of queries for something
            #  that could have a default
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('html_report', 1))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('isolate_id', 2))
            isolates_isosubfo_psql_tbl.insert_validation_indexes(('validation_type', 3))


def samples_to_validation_bigs(species: str) -> None:
    """
    Send samples in the badqc_sample and resequencing collection to be validated on BIGSdb
    :param species: commonly used bioit species name: either genus or specific like stec
    :return: None
    """
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        mongo_config_data = yaml.safe_load(handle)

    bigsdb_config_data = get_bigsdb_config_data()

    try:

        # Open collections
        mongoinit = MongoInitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections(mongo_config_data, species)

        # fetch all documents in the bad samples of the species
        update_collection = mongoinit.initialise_update_collection(mongo_config_data, species)
        query = update_collection.find_one({'metadata': 'last_validation_to_bigs_update'})
        if query:
            last_run_date = query['last_update_date']
        else:
            last_run_date = datetime.datetime(1970, 1, 1)
            update_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
                {'metadata': 'last_validation_to_bigs_update', 'last_update_date': last_run_date})
        current_date = datetime.datetime.utcnow()
        bad_samples = list(isolates_badqc_collection.find({'creation_date': {'$gt': last_run_date}}))
        #todo: add a date for synchronization with mongo and fetch only samples older than the date of last update
        _insert_submission_bigs(bad_samples, 'bad_quality', species)
        resequencing_samples = list(isolates_resequencing_collection.find({'creation_date': {'$gt': last_run_date}}))
        _insert_submission_bigs(resequencing_samples, 'resequencing', species)
        #update last date of update
        update_collection.with_options(write_concern=WriteConcern(w="majority")).find_one_and_update(
            {'metadata': 'last_validation_to_bigs_update'}, {'$set': {'last_update_date': current_date}})
    
    except Exception as exceptionmessage:
        send_email(f"{Path(__file__).name} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config_data['mail'])
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")
