import argparse
import logging
import sys
import os
import yaml
from pathlib import Path
import smtplib
from email.message import EmailMessage
import socket
import traceback
import datetime
from pymongo.write_concern import WriteConcern

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.util.mongo_initialisation import MongoInitialisation
from MongoDB.config import MONGO_CONFIG
from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from bioit_custom_scripts.config import BIGSDB_CONFIG

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

def _insert_submission_bigs(cur_isolates: object, sample_docs: list[dict], validation_type: str) -> None:
    """
    Inserts a given list of submissions into bigsdb
    :param cur_isolates: isolates db cursor object
    :param sample_docs: list of documents to be submitted
    :param validation_type: either bad_quality or resequencing
    :return:
    """
    for doc in sample_docs:
        cur_isolates.execute(f"INSERT INTO submissions (id, "
                             f"type,submitter, date_submitted, "
                             f"datestamp, status, email, validation_type)"
                             f"VALUES ((SELECT CASE WHEN (SELECT MAX(id::int) FROM submissions) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id::int) FROM submissions)+1) END), "
                             f"'isolates', 1, (SELECT CURRENT_DATE), "
                             f"(SELECT CURRENT_DATE), 'pending', true, '{validation_type}')")
        # todo need to set a proper method to build links based on the sample to transfer
        # for testing purposes
        html_path = 'http://bioit-bigs-dev.sciensano.be/galaxyreports/listeria/110-001_S68_L001/report.html'
        # dev code, not set yet
        html_path = str(html_path).replace('/reports/', '/galaxyreports/')
        html_link = f'<p><a href="{html_path}" target="_blank"> html report</a></p>'
        # end of dev code
        cur_isolates.execute(f"INSERT INTO isolate_submission_isolates (submission_id, index, field, value) "
                             f"VALUES "
                             f"((SELECT MAX(id::int) FROM submissions), 1, 'html_report', '{html_link}'), "
                             f"((SELECT MAX(id::int) FROM submissions), 1, 'isolate_id', '{doc['_id']}'), "
                             f"((SELECT MAX(id::int) FROM submissions),1, 'validation_type', '{validation_type}')"
                             )
        cur_isolates.execute(f"INSERT INTO isolate_submission_field_order (submission_id,field,index)"
                             f"VALUES "
                             f"((SELECT MAX(id::int) FROM submissions), 'html_report', 1), "
                             f"((SELECT MAX(id::int) FROM submissions), 'isolate_id', 2), "
                             f"((SELECT MAX(id::int) FROM submissions), 'validation_type', 3)"
                             )

def samples_to_validation_bigs(species: str) -> None:
    """
    Send samples in the badqc_sample and resequencing collection to be validated on BIGSdb
    :param species: the species of the database to send the bad samples from
    :return: None
    """
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config = yaml.safe_load(handle)
    try:

        # Open collections
        mongoinit = MongoInitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections(config_data, species)

        # Connect to db and create cursor
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        # fetch all documents in the bad samples of the species
        update_collection = mongoinit.initialise_update_collection(config_data, species)
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
        _insert_submission_bigs(cur_isolates, bad_samples, 'bad_quality')
        resequencing_samples = list(isolates_resequencing_collection.find({'creation_date': {'$gt': last_run_date}}))
        _insert_submission_bigs(cur_isolates, resequencing_samples, 'resequencing')
        #update last date of update
        update_collection.with_options(write_concern=WriteConcern(w="majority")).find_one_and_update(
            {'metadata': 'last_validation_to_bigs_update'}, {'$set': {'last_update_date': current_date}})

        DatabaseConnection().close_connections(con_isolates, con_seqdef)
    except Exception as exceptionmessage:
        send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config['mail'])
        raise Exception(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}")
