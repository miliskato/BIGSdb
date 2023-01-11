"""
This script is reference by SubmitPage.pm in the lib/BIGSdb folder, if its location is modified, it needs to be modified there as well
"""

#!/usr/bin/env python
import argparse
import logging
import sys
import os
import yaml
import smtplib
from email.message import EmailMessage
import socket
import traceback
import re
import json
import datetime
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from bioit_custom_scripts.config import BIGSDB_CONFIG
from MongoDB.util.mongo_initialisation import MongoInitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.mainmongo import MainMongo

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

def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--db', required=True, type=str)
    return argument_parser.parse_args()

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = parse_arguments()
    species = re.sub('bigsdb_|_isolates','', args.db)
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config = yaml.safe_load(handle)
    try:

        # Open collections
        mongoinit = MongoInitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = \
            mongoinit.initialise_collections(config_data, species)

        # Connect to db and create cursor
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        cur_isolates.execute(f"SELECT id, outcome, curator, validation_type FROM submissions WHERE status='closed'")
        query = cur_isolates.fetchall()
        if query:  # todo 09/01/2023 MK I think this is a dangerous approach. If at some point no connection can be made between bigs and mongo, a delay will be acquired. I would modify this to be a for loop, combined with a flagfile to say that this script is running which also contains the start time, if the start time is longer than 10 min ago remove it and restart
            #retrieve id of the isolate and curator id from BIGSdb
            id = query[0][0]
            outcome = query[0][1]
            curator_id = query[0][2]
            validation_type = query[0][3]
            if validation_type == 'bad_quality':
                results_type = 'badqc_validated'
            elif validation_type == 'resequencing':
                results_type = 'resequencing_validated'
            else:
                results_type = '?'  # in order to not have issue 'variable referenced before assignment' and in order to leave possibility open
            # todo curator name could be queried in the previous query already as a join, same for isolate_id
            cur_isolates.execute(f"SELECT user_name FROM users WHERE id='{curator_id}'")
            curator_name = cur_isolates.fetchall()[0][0]
            cur_isolates.execute(f"SELECT value FROM isolate_submission_isolates WHERE "
                                                    f"submission_id='{id}' AND field='isolate_id' ")
            isolate_id = cur_isolates.fetchall()[0][0]
            #GO into mongo DB
            validation = {
                'outcome': outcome,
                'curator': curator_name
            }
            # Note on the behaviour of the script: This scripts runs when a sample has been validated on BIGSdb by a
            # curator. Main steps:
            # 1) The validation outcome is added into the results of the samples (curator name and outcome).
            # 2) If the outcome is 'good', the script mainmongo.py is called in with specific options (see below).
            # In this mode, the mainmongo will retrieve the sample to insert in the isolate collection. It will also
            # add the date of validation (which can't be passed though the json as the date object is not serializable).
            #In addition, path to fasta and vcfile are also added.
            # If the outcome is bad, the date is added to the dict of the validation outcome and this dict is saved into the
            # results of the badqc_isolates
            if outcome == 'good':
                MainMongo(isolate_id, species, results_type, subvaldict=validation)
            else:
                validation['date'] = datetime.datetime.utcnow()
                def _remove_id_from_document_to_be_unique_again_if_bad(collection_in: object) -> None:
                    """
                    This function modifies the document to not have the unique bioit identifier anymore, but the MongoDB autogenerated one.
                    Appearently the only or easiest way to do this is to reinsert the document.
                    The goal of this manipulation is to be able to insert new resequencings or bad samples.
                    Additionally it adds the validation dict
                    :param collection_in: collection document is in
                    :return: None
                    """
                    negatively_validated_document = dict(collection_in.with_options(read_concern=ReadConcern(w="majority")).find_one({'_id': isolate_id}))
                    negatively_validated_document['validation'] = validation
                    negatively_validated_document.pop('_id')
                    collection_in.with_options(write_concern=WriteConcern(w="majority")).insert_one(negatively_validated_document)  # Modified doc
                    collection_in.with_options(write_concern=WriteConcern(w="majority")).delete_one({'_id': isolate_id})  # Unmodified doc
                if validation_type == 'bad_quality':
                    _remove_id_from_document_to_be_unique_again_if_bad(isolates_badqc_collection)
                elif validation_type == 'resequencing':
                    _remove_id_from_document_to_be_unique_again_if_bad(isolates_resequencing_collection)
            #update status once everything is finished
            cur_isolates.execute(f"UPDATE submissions SET status='validation_sent_to_bioit_platform' WHERE id='{id}'")

            query_isolate_id = cur_isolates.execute(f"SELECT value FROM isolate_submission_isolates WHERE submission_id='{id}' AND field='isolate_id' ")
            isolate_id = cur_isolates.fetchall()[0][0]
            cur_isolates.execute(f"UPDATE submissions SET status='validation_sent_to_bioit_platform' WHERE id='{id}'")
        DatabaseConnection().close_connections(con_isolates, con_seqdef)
    except Exception as exceptionmessage:
        send_email(f"{os.path.basename(__file__)}: sample validation to mongo fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config['mail'])
        raise Exception(f"{os.path.basename(__file__)}: sample validation to mongo fail on host {socket.gethostname()}")
