import argparse
import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urljoin
import concurrent.futures
import os
import sys
import socket
import shutil
import requests
import yaml
import psycopg2
import subprocess
import datetime
import traceback
import smtplib
from email.message import EmailMessage
import datetime

from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern

PYTHONPATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.reanalysis.command.command import Command
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.reanalysis import MONGO_REANALYSIS_CONFIG

ALTERNATE_CONNECTION_STRING = 'mongodb+srv://mikelchtermans:YMFOH4BLF1U79dDk@hera-bioit-trial.vajezh0.mongodb.net'  # do not change

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='eg /home/BIGSdb/3.9PythonVenv/bin/python3.9')
    return parser.parse_args()

def _send_email(subject: str, content: str, config: dict) -> None:
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

if __name__ == '__main__':

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    if config_data.get('CONNECTION_STRING_BASE') and config_data.get('dtap'):
        config_data['CONNECTION_STRING_BASE'] = ALTERNATE_CONNECTION_STRING
    else:
        raise Exception('has config modified?')

    try:

        args = _parse_arguments()

        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Open collections
        mongoinit = Mongoinitialisation()
        isolates_collection, isolateresults_collection, isolates_badqc_collection = \
            mongoinit.initialise_collections(config_data, 'listeria')
        hashed_ad_collection = mongoinit.initialise_hashing_collection(config_data, 'listeria')
        st_collection, cluster_membership_collection = \
            mongoinit.initialise_clustering_collections(config_data, 'listeria')
        update_collection = mongoinit.initialise_update_collection(config_data, 'listeria')

        # as a first step I would drop the db if query less than 5 results else raise exception
        documents_count = isolates_collection.count_documents({})
        if documents_count > 5:
            raise Exception('Are you sure you are looking at the right database using the right connection string?')
        else:
            isolates_collection.drop()
            isolateresults_collection.drop()
            isolates_badqc_collection.drop()
            hashed_ad_collection.drop()
            st_collection.drop()
            cluster_membership_collection.drop()
            update_collection.drop()


        def create_mainmongo_cmd(results_type: str, filename: str) -> object:
            """

            :param results_type: either new_isolate or reanalysis
            :param filename: filename in inputfiles
            :return:
            """
            # Create command insertion MongoDB
            source = os.path.dirname(__file__)
            parent = os.path.join(source, '../')
            base_command = ' '.join([
                f"{args.pyvenvpythonpath}",
                f"{os.path.join(parent, 'mainmongo.py')}",
                f'--results_type {results_type}',
                f'--technical_id test_mainmongo',
                f"--jsonfilepath {'/'.join([source, 'inputfiles', filename])}",
                f"--species listeria",
                f"--alternate_connection_string {ALTERNATE_CONNECTION_STRING}"
            ])
            if results_type == 'new_isolate':
                base_command += f" --fastafilepath {'/'.join([source, 'inputfiles', 'listeria_assembly_filtered.fasta'])}"
            command = Command(base_command)
            return command

        # Add the new_isolate:
        new_isolate_cmd = create_mainmongo_cmd('new_isolate', 'report_version_1_1.json')
        logging.info(f"new isolate command: {new_isolate_cmd._command}")
        new_isolate_cmd.run(os.getcwd())

        # test hash replacer
        source = os.path.dirname(__file__)
        parent = os.path.join(source, '../')
        base_command = ' '.join([
            f"{args.pyvenvpythonpath}",
            f"{os.path.join(parent, 'hash_replacer.py')}",
            f'--species listeria',
            f'--scheme cgmlst',
            f'--alternate_connection_string {ALTERNATE_CONNECTION_STRING}'
        ])
        command = Command(base_command)
        command.run(Path(os.getcwd()))

        # Add the dummy reanalysis results:
        # the integers appendices of the files indicate the results version and changed version, so: resultsversion_changedversion
        for dummy_reanalysis_file in ['report_version_2_2.json', 'report_version_3_3.json', 'report_version_4_4.json', 'report_version_5_4.json']:
            reanalysis_cmd = create_mainmongo_cmd('reanalysis', dummy_reanalysis_file)
            logging.info(f"reanalysis insertion command: {reanalysis_cmd._command}")
            reanalysis_cmd.run(os.getcwd())

        # test reanalysis
        source = os.path.dirname(__file__)
        parent = os.path.join(source, '../')
        base_command = ' '.join([
            f"{args.pyvenvpythonpath}",
            f"{os.path.join(parent, 'reanalysis', 'reanalysis.py')}",
            f'--species listeria',
            f'--maximal_analysis_date 2030-01-01',
            f'--pyvenvpythonpath {args.pyvenvpythonpath}',
            f'--alternate_connection_string {ALTERNATE_CONNECTION_STRING}'
        ])
        command = Command(base_command)
        command.run(Path(os.getcwd()))

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)}: mongo testing fail on {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
