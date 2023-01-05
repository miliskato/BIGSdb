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

from MongoDB.util.mongo_initialisation import Mongoinitialisation
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


def bad_samples_to_validation_bigs(species: str) ->None:
    """
    Send samples in the badqc_sample collection to be validated on BIGSdb
    :param species: the species of the database to send the bad samples from
    :return: None
    """
    #for testing purposes
    html_path = 'http://bioit-bigs-dev.sciensano.be/galaxyreports/listeria/110-001_S68_L001/report.html'

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config = yaml.safe_load(handle)
    try:

        # Open collections
        mongoinit = Mongoinitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection = mongoinit.initialise_collections(config_data, species)


        # Connect to db and create cursor
        cur_isolates, cur_seqdef = DatabaseConnection().open_database_connections(species)

        # fetch all documents in the bad samples of the species
        update_collection = mongoinit.initialise_update_collection(config_data, species)
        query = update_collection.find_one({'metadata': 'last_bad_samples_update'})
        if query:
            last_run_date = query['last_update_date']
        else:
            last_run_date = datetime.datetime(1970, 1, 1)
            update_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
                {'metadata': 'last_bad_samples_update', 'last_update_date': last_run_date})
        current_date = datetime.datetime.utcnow()
        mongo_query = isolates_badqc_collection.find({'creation_date': {'$gt': last_run_date}})
        #todo: add a date for synchronization with mongo and fetch only samples older than the date of last update
        bad_samples = []
        for doc in mongo_query:
            bad_samples.append(doc)

        cur_isolates.execute(f"SELECT max(id::int ) FROM submissions")
        highest_sub_id = cur_isolates.fetchall()[0][0]
        if highest_sub_id:
            highest_sub_id = int(highest_sub_id)
        else:
            highest_sub_id = 0
        for doc in bad_samples:
            highest_sub_id = highest_sub_id + 1
            cur_isolates.execute(f"INSERT INTO submissions  (id,type,submitter,date_submitted,datestamp,status,email)"
                                 f"VALUES ({highest_sub_id}, 'isolates', 1, (SELECT CURRENT_DATE), "
                                 f"(SELECT CURRENT_DATE), 'pending', true)")
            #todo need to set a proper method to build links based on the sample to transfer
            #dev code, not set yet
            html_path = str(html_path).replace('/reports/','/galaxyreports/')
            html_link = f'<p><a href="{html_path}" target="_blank"> html report</a></p>'
            #end of dev code
            field = 'html_report'
            cur_isolates.execute(f"INSERT INTO isolate_submission_isolates (submission_id, index, field, value) "
                                 f"VALUES ({highest_sub_id},1, '{field}', '{html_link}')")
            cur_isolates.execute(f"INSERT INTO isolate_submission_field_order (submission_id,field,index)"
                                 f"VALUES ({highest_sub_id}, '{field}',1)")
            field2 = 'isolate_id'
            cur_isolates.execute(f"INSERT INTO isolate_submission_isolates (submission_id, index, field, value) "
                                 f"VALUES ({highest_sub_id},1, '{field2}', '{doc['_id']}')")
            cur_isolates.execute(f"INSERT INTO isolate_submission_field_order (submission_id,field,index)"
                                 f"VALUES ({highest_sub_id}, '{field2}',2)")
            #update last date of update
            update_collection.with_options(write_concern=WriteConcern(w="majority")).find_one_and_update(
                {'metadata': 'last_bad_samples_update'}, {'$set': {'last_update_date': current_date}})

    except Exception as exceptionmessage:
        send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config['mail'])
        raise Exception(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}")