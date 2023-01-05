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
from typing import Dict

from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern

PYTHONPATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.util.command.command import Command
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.reanalysis import MONGO_REANALYSIS_CONFIG
from MongoDB.mainmongo import mainmongo
from MongoDB.tempid_replacer import tempid_replacer
from MongoDB.reanalysis.reanalysis_noslurm import reanalysis_noslurm
from MongoDB.reanalysis.reanalysis_triggers.reanalysis_triggers import reanalysis_triggers

ALTERNATE_CONNECTION_STRING = 'mongodb+srv://mikelchtermans:YMFOH4BLF1U79dDk@hera-bioit-trial.vajezh0.mongodb.net'  # do not change


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
        raise Exception('was config modified?')

    try:

        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Open collections
        mongoinit = Mongoinitialisation()
        isolates_collection, isolateresults_collection, isolates_badqc_collection = \
            mongoinit.initialise_collections(config_data, 'listeria')
        hashed_ad_collection = mongoinit.initialise_hashing_collection(config_data, 'listeria')
        st_collection, cluster_membership_collection, cluster_merging_collection = \
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
            cluster_merging_collection.drop()
            update_collection.drop()


        def create_mainmongo_arguments_dict(results_type: str, filename: str) -> Dict[str, str]:
            """

            :param results_type: either new_isolate or reanalysis
            :param filename: filename in inputfiles
            :return:
            """
            # Create command insertion MongoDB
            source = os.path.dirname(__file__)
            arguments = {'technical_id': 'test_mainmongo',
                         'species': 'listeria',
                         'results_type': results_type,
                         'jsonfilepath': '/'.join([source, 'inputfiles', filename]),
                         'alternate_connection_string': ALTERNATE_CONNECTION_STRING}
            if results_type == 'new_isolate':
                arguments['fastafilepath'] = '/'.join([source, 'inputfiles', 'listeria_assembly_filtered.fasta'])
            return arguments

        # Add the new_isolate:
        new_isolate_args = create_mainmongo_arguments_dict('new_isolate', 'report_version_1_1.json')
        mainmongo(**new_isolate_args)

        # test hash replacer
        tempid_replacer('cgmlst', 'listeria', alternate_connection_string=ALTERNATE_CONNECTION_STRING)

        # Add the dummy reanalysis results:
        # the integers appendices of the files indicate the results version and changed version, so: resultsversion_changedversion
        for dummy_reanalysis_file in ['report_version_2_2.json', 'report_version_3_3.json', 'report_version_4_4.json', 'report_version_5_4.json']:
            reanalysis_args = create_mainmongo_arguments_dict('reanalysis', dummy_reanalysis_file)
            mainmongo(**reanalysis_args)

        # test reanalyis triggers and reanalysis
        reanalysis_triggers('listeria', 6, alternate_connection_string=ALTERNATE_CONNECTION_STRING)

        # test reanalysis
        reanalysis_noslurm('listeria', '2030-01-01', '2000-01-01', alternate_connection_string=ALTERNATE_CONNECTION_STRING)

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        raise Exception(f"{os.path.basename(__file__)} fail on {socket.gethostname()}")
