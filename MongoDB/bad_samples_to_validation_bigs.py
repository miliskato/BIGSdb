import subprocess
import argparse
import logging
import sys
import os
import yaml
import json
from pathlib import Path
import datetime
from pymongo.read_concern import ReadConcern
import smtplib
from email.message import EmailMessage
import socket
import traceback

from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG
from bioit_custom_scripts.components.databaseconnection import Database_connection
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

def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    argument_parser.add_argument('--html_path', type=Path, required=True)
    return argument_parser.parse_args()

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config = yaml.safe_load(handle)
    try:

        # Open collections
        mongoinit = Mongoinitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(config_data, args.species)

        # Connect to db and create cursor
        cur_isolates, cur_seqdef = Database_connection().open_database_connections(args.species)

        # fetch all documents in the bad samples of the species
        mongo_query = isolates_badqc_collection.find({}) #todo: add a date for synchronization with mongo and fetch only samples older than the date of last update
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
            html_path = str(args.html_path).replace('/reports/','/galaxyreports/')
            html_link = f'<p><a href="{html_path}" target="_blank"> html report</a></p>'
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


    except Exception as exceptionmessage:
        send_email(f"{os.path.basename(__file__)}: mongo to bigs fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config['mail'])
