#!/usr/bin/env python
import argparse
import logging
import re
import shutil
import sys
import traceback
from pathlib import Path
from typing import List, Literal

from bioit_mongodb_scripts.util_azure.connect_azure import ConnectAzure

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    mutually_exclusive_group = argument_parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--db', type=str)
    mutually_exclusive_group.add_argument('--species', type=str, choices=MongoConfigProvider.get_currently_supported_species())
    argument_parser.add_argument('--technical_id', required=True, type=str)
    argument_parser.add_argument('--validation_type', required=True, type=str, choices=['null', 'good_quality', 'warning_quality', 'resequencing', 'rejected_isolate'])
    argument_parser.add_argument('--dtap', required=True, type=str, choices=['dev', 'test', 'acc', 'prod'])
    return argument_parser.parse_args()


class HtmlreportGeneration:
    """
    Generates a html report for a given isolate at a given results version
    """
    def __init__(self, species: str, technical_id: str, dtap: Literal['dev', 'test', 'acc', 'prod'],
                 validation_type: Literal['null', 'good_quality', 'warning_quality', 'resequencing', 'rejected_isolate']) -> None:
        """
        Initialises the class and runs the main function.
        See also argparse function for variables and their requiredness.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param technical_id: sample id/ isolates id
        :param dtap: dev, test, acc, or prod
        :return: None
        """
        # Input parameters
        self._species = species
        self._technical_id = technical_id
        self._mongo_config_provider = MongoConfigProvider(dtap)
        self._validation_type = validation_type

        # Connect to keyvault
        self._connection_azure = ConnectAzure(self._mongo_config_provider.dtap)

        # Parse config


        # Open collections
        self._mongoinit = MongoInitialisation(self._species, self._mongo_config_provider.get_azure_connection_string(self._species), self._mongo_config_provider.dtap)

        self._isolates_collection, self._old_isolateresults_collection, self._isolates_warningqc_collection, \
            self._isolates_resequencing_collection, self._isolates_goodqc_collection = \
            self._mongoinit.initialise_collections()
        self._rejected_isolates_collection = self._mongoinit.initialise_isolates_rejected_coreqc_collection()

        # Run main
        try:
            self._htmlreport_generation()
        except Exception as exceptionmessage:
            raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")

    def _htmlreport_generation(self):
        """
        Main function; generates the requested report version and returns it.
        :return: None
        """
        if self._validation_type == 'good_quality':
            requested_document = self._isolates_goodqc_collection.find_one({'_id': self._technical_id})
        elif self._validation_type == 'warning_quality':
            requested_document = self._isolates_warningqc_collection.find_one({'_id': self._technical_id})
        elif self._validation_type == 'resequencing':
            requested_document = self._isolates_resequencing_collection.find_one({'_id': self._technical_id})
        elif self._validation_type == 'rejected_isolate':
            requested_document = self._rejected_isolates_collection.find_one({'_id': self._technical_id})
        else:  # self._validation_type == 'null':
            requested_document = self._isolates_collection.find_one({'_id': self._technical_id})

        # Set the output dir
        dir_out = Path(self._mongo_config_provider.temp_dir) / self._mongo_config_provider.dtap / self._species / self._technical_id
        dir_out.rmdir()
        shutil.copytree(requested_document['report_directory'], str(dir_out))


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse config

    # Parse arguments
    args = parse_arguments()
    species = re.sub('bigsdb_|_isolates', '', args.db) if args.db else args.species

    # run main
    HtmlreportGeneration(species, args.technical_id, args.dtap, args.validation_type)
