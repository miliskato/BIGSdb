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

from bioit_mongodb_scripts.mainmongo import MainMongo
from bioit_mongodb_scripts.reanalysis.reanalysis_noslurm import reanalysis_noslurm
from bioit_mongodb_scripts.reanalysis.reanalysis_triggers.reanalysis_triggers import reanalysis_triggers
from bioit_mongodb_scripts.tempid_replacer import TempidReplacer
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


if __name__ == '__main__':

    # Parse config
    mongo_config_data = get_mongodb_config_data()

    if mongo_config_data.get('CONNECTION_STRING_AZURE') and mongo_config_data.get('dtap'):
        pass
    else:
        raise Exception('was config modified?')

    try:

        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Open collections
        mongoinit = MongoInitialisation('listeria', alternate_connection_string=True,
                                        mongo_config_data=mongo_config_data)
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = \
            mongoinit.initialise_collections()

        # as a security measure I would drop the db if query less than 5 results else raise exception
        documents_count = isolates_collection.count_documents({})
        if documents_count > 5:
            raise Exception('Are you sure you are looking at the right database using the right connection string?')
        else:
            # drop all collections in the database
            for coll_name in mongoinit.opened_mongo_database.list_collection_names():
                mongoinit.opened_mongo_database[coll_name].drop()

        def create_mainmongo_arguments_dict(results_type: str, filename: str) -> Dict[str, str]:
            """
            Creates a dictionary of the arguments necessary for mainmongo
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
                         'alternate_connection_string': True,
                         'mongo_config_data': mongo_config_data}
            if results_type == 'new_isolate':
                arguments['reportdirectorypath'] = '/'.join([source, 'inputfiles'])
                arguments['fastafilepath'] = '/'.join([source, 'inputfiles', 'listeria_assembly_filtered.fasta'])
            return arguments

        """
        Add new good isolate
        """
        new_isolate_args = create_mainmongo_arguments_dict('new_isolate', 'report_version_1_1.json')
        MainMongo(**new_isolate_args)

        new_isolate_args = create_mainmongo_arguments_dict('new_isolate', 'report_version_5_4.json')
        new_isolate_args['technical_id'] = 'test_mainmongo_2'
        MainMongo(**new_isolate_args)

        """
        Add new bad isolate
        """
        new_isolate_args = create_mainmongo_arguments_dict('new_isolate', 'bad_report_version_1_1.json')
        new_isolate_args['technical_id'] = 'test_mainmongo_bad'
        MainMongo(**new_isolate_args)

        """
        Test hash replacer
        """
        TempidReplacer('cgmlst', 'listeria', alternate_connection_string=True)

        """
        Test reanalysis insertion/ versioning
        """
        # the integers appendices of the files indicate the results version and changed version, so: resultsversion_changedversion
        for dummy_reanalysis_file in ['report_version_2_2.json', 'report_version_3_3.json', 'report_version_4_4.json', 'report_version_5_4.json']:
            reanalysis_args = create_mainmongo_arguments_dict('reanalysis', dummy_reanalysis_file)
            MainMongo(**reanalysis_args)

        """
        Test reanalysis triggers and reanalysis_noslurm
        """
        reanalysis_triggers('listeria', 6, alternate_connection_string=True)

        """
        Test reanalysis_noslurm
        """
        reanalysis_noslurm('listeria', '2030-01-01', '2000-01-01', alternate_connection_string=True)

    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")
