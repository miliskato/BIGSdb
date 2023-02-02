import logging
import os
import smtplib
import socket
import sys
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import Dict

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.config import MONGO_CONFIG
from bioit_mongodb_scripts.mainmongo import MainMongo
from bioit_mongodb_scripts.tempid_replacer import TempidReplacer
from bioit_mongodb_scripts.reanalysis.reanalysis_noslurm import reanalysis_noslurm
from bioit_mongodb_scripts.reanalysis.reanalysis_triggers.reanalysis_triggers import reanalysis_triggers


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
        pass
    else:
        raise Exception('was config modified?')

    try:

        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Open collections
        mongoinit = MongoInitialisation('listeria', alternate_connection_string=True)
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = \
            mongoinit.initialise_collections()
        hashed_ad_collection = mongoinit.initialise_hashing_collection()
        st_collection, cluster_membership_collection, cluster_merging_collection = \
            mongoinit.initialise_clustering_collections()
        update_collection = mongoinit.initialise_update_collection()
        headers_collection = mongoinit.initialise_headers_collection()

        # as a first step I would drop the db if query less than 5 results else raise exception
        documents_count = isolates_collection.count_documents({})
        if documents_count > 5:
            raise Exception('Are you sure you are looking at the right database using the right connection string?')
        else:
            isolates_collection.drop()
            old_isolateresults_collection.drop()
            isolates_badqc_collection.drop()
            hashed_ad_collection.drop()
            st_collection.drop()
            cluster_membership_collection.drop()
            cluster_merging_collection.drop()
            update_collection.drop()
            headers_collection.drop()


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
                         'alternate_connection_string': True}
            if results_type == 'new_isolate':
                arguments['reportdirectorypath'] = '/'.join([source, 'inputfiles'])
                arguments['fastafilepath'] = '/'.join([source, 'inputfiles', 'listeria_assembly_filtered.fasta'])
            return arguments

        # Add the new_isolate:
        new_isolate_args = create_mainmongo_arguments_dict('new_isolate', 'report_version_1_1.json')
        MainMongo(**new_isolate_args)

        # test hash replacer
        TempidReplacer('cgmlst', 'listeria', alternate_connection_string=True)

        # # Add the dummy reanalysis results:
        # # the integers appendices of the files indicate the results version and changed version, so: resultsversion_changedversion
        # for dummy_reanalysis_file in ['report_version_2_2.json', 'report_version_3_3.json', 'report_version_4_4.json', 'report_version_5_4.json']:
        #     reanalysis_args = create_mainmongo_arguments_dict('reanalysis', dummy_reanalysis_file)
        #     MainMongo(**reanalysis_args)

        # # test reanalyis triggers and reanalysis
        # reanalysis_triggers('listeria', 6, alternate_connection_string=True)
        #
        # # test reanalysis
        # reanalysis_noslurm('listeria', '2030-01-01', '2000-01-01', alternate_connection_string=True)

    except Exception as exceptionmessage:
        _send_email(f"{Path(__file__).name} fail on {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        raise Exception(f"{Path(__file__).name} fail on {socket.gethostname()}")
