#!/usr/bin/env python
import argparse
import logging
import sys
import os
from pathlib import Path
import yaml
import smtplib
from email.message import EmailMessage
import socket
import traceback
import re
import json
import datetime
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
from bioit_custom_scripts.components.databaseconnection import Database_connection
from bioit_custom_scripts.config import BIGSDB_CONFIG
from MongoDB.reanalysis.command.command import Command

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
        mongoinit = Mongoinitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection = \
            mongoinit._initialise_collections(config_data, species)

        # Connect to db and create cursor
        cur_isolates, cur_seqdef = Database_connection().open_database_connections(species)

        cur_isolates.execute(f"SELECT id, outcome, curator FROM submissions WHERE status='closed'")
        query = cur_isolates.fetchall()
        if query:
            #retrieve id of the isolate and curator id from BIGSdb
            id = query[0][0]
            outcome = query[0][1]
            curator_id = query[0][2]
            cur_isolates.execute(f"SELECT user_name FROM users WHERE id='{curator_id}'")
            curator_name = cur_isolates.fetchall()[0][0]
            query_isolate_id = cur_isolates.execute(f"SELECT value FROM isolate_submission_isolates WHERE "
                                                    f"submission_id='{id}' AND field='isolate_id' ")
            isolate_id = cur_isolates.fetchall()[0][0]
            #GO into mongo DB
            validation = {
                'outcome': outcome,
                'curator': curator_name
            }
            #write doc to tmp
            # with open("/home/bebergk/tmp_isolate_sub.json", "w") as write_file:
            #     json.dump(json_sample, write_file, indent=4)
            if outcome=='good':
                command_line = f"export MODULEPATH=/etc/lmod/modules;" \
                               f"source /etc/profile.d/lmod.sh;" \
                               f"ml mongo_bigs_dbs;" \
                               f"mainmongo.py " \
                               f"--dict '{json.dumps(validation)}' " \
                               f"--species {species} " \
                               f"--results_type badqc_validated " \
                               f"--fastafilepath na " \
                               f"--vcffilepath na " \
                               f"--technical_id {isolate_id}"
                command = Command(command_line)
                command.run(Path(os.getcwd()))
            else:
                validation['date'] = datetime.datetime.utcnow()
                isolates_badqc_collection.update({'_id': isolate_id}, {'$set': validation})
            #update status once everything is finished
            cur_isolates.execute(f"UPDATE submissions SET status='validation_sent_to_bioit_platform' WHERE id='{id}'")

    except Exception as exceptionmessage:
        send_email(f"{os.path.basename(__file__)}: mongo to bigs fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config['mail'])