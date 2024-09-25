import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Dict

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.mainmongo import MainMongo
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
        mongoinit = MongoInitialisation('listeria', selected_connection_string='CONNECTION_STRING_ALTERNATE',
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
                         'connection_string': 'CONNECTION_STRING_ALTERNATE',
                         'pipeline_hash': 'testtest',
                         'mongo_config_data': mongo_config_data}
            if results_type == 'new_isolate':
                arguments['reportdirectorypath'] = '/'.join([source, 'inputfiles'])
                arguments['fastafilepath'] = '/'.join([source, 'inputfiles', 'listeria_assembly_filtered.fasta'])
                arguments['technical_metadata_path'] = '/'.join([source, 'inputfiles', 'technical_metadata.json'])
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
        TempidReplacer('cgmlst', 'listeria', connection_string='CONNECTION_STRING_ALTERNATE')

    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")
