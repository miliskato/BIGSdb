#!/usr/bin/env python
import argparse
import json
import logging
import re
import shutil
import socket
import sys
import tempfile
import traceback
from pathlib import Path
from typing import List, Optional

from bioit_mongodb_scripts.util_azure.connect_azure import ConnectAzure

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    mutually_exclusive_group = argument_parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--db', type=str)
    mutually_exclusive_group.add_argument('--species', type=str, choices=specieslist)
    argument_parser.add_argument('--technical_id', required=True, type=str)
    argument_parser.add_argument('--validation_type', required=True, type=str, choices=['null', 'bad_quality', 'resequencing'])
    mutually_exclusive_group2 = argument_parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group2.add_argument('--changed_version', type=int)
    mutually_exclusive_group2.add_argument('--analysis_date', type=str)
    argument_parser.add_argument('--dtap', required=True, type=str, choices=['dev', 'test', 'acc', 'prod'])
    return argument_parser.parse_args()


class HtmlreportGeneration:
    """
    Generates a html report for a given isolate at a given results version
    """
    def __init__(self, species: str, technical_id: str, dtap: str, validation_type: str, changed_version: Optional[int] = None,
                 analysis_date: Optional[str] = None) -> None:
        """
        Initialises the class and runs the main function.
        See also argparse function for variables and their requiredness.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param technical_id: sample id/ isolates id
        :param dtap: dev, test, acc, or prod
        :param validation_type: null, bad_quality or resequencing
        :param changed_version: changed version of the desired report
        :param analysis_date: desired date of the report (usually today but can query previous versions too (used in BIGSdb)),
        if it doesn't exist, get the closest more recent report date
        :return: None
        """
        # Input parameters
        self._species = species
        self._technical_id = technical_id
        self._dtap = dtap
        self._validation_type = validation_type
        self._changed_version = changed_version
        self._analysis_date = analysis_date

        # Parameter compatibility checks
        if (not self._changed_version and not self._analysis_date) or (self._changed_version and self._analysis_date):
            raise ValueError('Exactly one of both changed_version or analysis_date must be provided!')
        if self._changed_version and not isinstance(self._changed_version, int):
            raise ValueError('if changed_version is searchkey; searchvalue must be integer')
        if self._analysis_date and not isinstance(self._analysis_date, str) and not re.match(r'^\d{4}-\d{2}-\d{2}$', self._analysis_date):
            raise ValueError('if analysis_date is searchkey; searchvalue must be string in YYYY-MM-DD format')
        if self._dtap not in ['dev', 'test', 'acc', 'prod']:
            raise ValueError('dtap must be one of dev, test, acc, or prod')
        if self._validation_type not in ['null', 'bad_quality', 'resequencing']:
            raise ValueError('validation_type must be one of null, bad_quality, or resequencing')
        if self._validation_type != 'null' and not self._analysis_date:
            raise ValueError('if validation type is not null, need an analysis date')

        # Connect to keyvault
        self._connection_azure = ConnectAzure(self._dtap)

        # Parse config
        self._mongo_config_data = get_mongodb_config_data()

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                              alternate_dtap=self._dtap,
                                              alternate_connection_string=self._connection_azure.get_secret_value('MONGODB-CONNECTION-STRING'))
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, \
            self._isolates_resequencing_collection = self._mongoinit.initialise_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()

        # Open querying class instance
        self._mongoquerying = Mongoquerying()

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
        if self._validation_type == 'bad_quality':
            requested_document = self._isolates_badqc_collection.find_one({'_id': self._technical_id, 'latest_analysis_date': self._analysis_date})
        elif self._validation_type == 'resequencing':
            requested_document = self._isolates_resequencing_collection.find_one({'_id': self._technical_id, 'latest_analysis_date': self._analysis_date})
        else:  # self._validation_type == 'null':
            requested_document = self._mongoquerying.get_any_results_version(
                self._technical_id, 'analysis_date' if self._analysis_date else 'changed_version',
                self._analysis_date if self._analysis_date else self._changed_version,
                self._isolates_collection, self._old_isolateresults_collection, self._headers_collection)

        # Set the output dir
        dir_out = Path(self._mongo_config_data['temp_dir']) / self._dtap / self._species / '_'.join(
            [self._technical_id, self._analysis_date if self._analysis_date else str(self._changed_version)])

        if requested_document['results'].get('results_version') and not requested_document['results']['results_version'] == 1: # badqc and reseq isolates do not have a results_version
            dir_out.mkdir(parents=True, exist_ok=True)
            with self.__create_temp_dir('temp_reporting') as dir_temp:
                # Dump the required json file
                jsonfile = Path(dir_temp) / f"{self._technical_id}_temp.json"
                with jsonfile.open('w') as handle:
                    handle.write(json.dumps(requested_document['results']))

                # Create the command to re-analyze the datasets
                base_command = ' '.join([
                    f"module load {self._mongo_config_data['htmlreporterpipeline']['lmod']}; ",
                    f"{self._mongo_config_data['htmlreporterpipeline']['main_script']} ",
                    f'--json_file {jsonfile} ',
                    f"--sample_files_dir {requested_document['report_directory']} "
                    f'--sample-name {self._technical_id} '
                    f'--output-dir {dir_out} ',
                    f"--output-html {dir_out / 'report.html'} ",
                    f"--output-tsv {dir_out / 'report.tsv'} ",
                    f'--working-dir {dir_temp} ',
                ])
                command = Command(base_command)

                # run the command
                command.run(dir_temp)

                if command.returncode != 0:
                    # dir_out seems to get removed by Camel; therefore recreate it here before moving the camel.log
                    dir_out.mkdir(parents=True, exist_ok=True)
                    # Moving the log to the report dir because debugging is pretty hard with a python temp dir
                    shutil.copyfile(Path(dir_temp) / 'camel.log', dir_out / 'camel.log')
                    raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: {command.stderr}")
        else:  # if requested_document['results_version'] == 1:
            shutil.copytree(requested_document['report_directory'], str(dir_out))
            pass

    def __create_temp_dir(self, prefix: str) -> tempfile.TemporaryDirectory:
        """
        Creates a temporary directory.
        :param prefix: Directory prefix
        :return: Path to temporary directory
        """
        return tempfile.TemporaryDirectory(prefix=prefix, dir=self._mongo_config_data['temp_dir'])


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])
    species = re.sub('bigsdb_|_isolates', '', args.db) if args.db else args.species

    # run main
    HtmlreportGeneration(species, args.technical_id, args.dtap, args.validation_type, args.changed_version, args.analysis_date)
