"""
This script is referenced by SubmitPage.pm in the lib/BIGSdb folder,
if the location of this script is modified, it needs to be modified there as well
"""

import argparse
import datetime
import logging
import re
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pymongo.collection import Collection
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSubmissions
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_mongodb_scripts.mainmongo import MainMongo
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.model.json_model import MongoRecordDict


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    mutually_exclusive_group = argument_parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--db', type=str)
    mutually_exclusive_group.add_argument('--species', type=str, choices=specieslist)
    argument_parser.add_argument('--sub_id', required=True, type=int)
    return argument_parser.parse_args()


class SampleValidationToMongo:
    """
    This class is used to send validation metadata from Bigsdb to MongoDB and move samples
    from the goodqc, resequencing or warningqc collection to the isolates collection.
    """
    def __init__(self, species: str, sub_id: int) -> None:
        """
        Initialises the class and runs the main function.
        See also argparse function for variables and their requiredness.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param sub_id: id of the submission in the submissions table
        :return: None
        """
        # Input parameters
        self._sub_id = sub_id
        self._species = species

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, selected_connection_string='CONNECTION_STRING_AZURE')
        self._isolates_collection, _, self._isolates_warningqc_collection, self._isolates_resequencing_collection, \
            self._isolates_goodqc_collection = self._mongoinit.initialise_collections()

        # open local mongo instance to get the mapping
        self._mongoinit_local = MongoInitialisation(self._species, selected_connection_string='CONNECTION_STRING_LOCAL')
        self._mapping_collection = self._mongoinit_local.initialise_mapping_table_collection()

        # Run main
        try:
            self._sample_validation_to_mongo()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name} fail on host {socket.gethostname()}")
            raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")

    def _sample_validation_to_mongo(self) -> None:
        """
        This script runs when a sample has been validated on BIGSdb by a curator. Main steps:
        1) The validation outcome is added into the results of the samples (curator name and outcome).
        2) If the outcome is 'good', the script mainmongo.py is called in with specific options (see below).
        In this mode, the mainmongo will retrieve the sample to insert in the isolate collection. It will also
        add the date of validation (which can't be passed through the json as the date object is not serializable).
        In addition, path to fasta and vcffile are also added.
        If the outcome is bad, the date is added to the dict of the validation outcome and this dict is saved into the
        results of the warningqc_isolates or goodqc_isolates
        :return: None
        """
        # Connect to db and create cursor
        with TblSubmissions(self._species) as self._isolates_submissions_psql_tbl:
            query: List[Tuple[Any]] = self._isolates_submissions_psql_tbl.select_closed_submission((str(self._sub_id),))
            if query:
                # retrieve id of the isolate and curator id from BIGSdb
                isolatename: str = query[0][1]
                outcome: str = query[0][2]
                curator_mailadress: str = query[0][3]
                quality: str = query[0][4]
                resequencing: bool = query[0][5]
                results_type = self.__get_results_type(quality, resequencing)  # goodqc_validated, warningqc_validated or resequencing_validated
                pseudo_id = self._mapping_collection.find_one({"_id": isolatename})['pseudo_id']
                # GO into MongoDB so type in Mongo might be either warningqc or resequencing
                validation_dict = {
                    'outcome': outcome,
                    'curator': curator_mailadress,
                    'type': results_type.split('_')[0],
                    'date': datetime.datetime.now(datetime.timezone.utc).strftime('%d/%m/%Y - %X')
                }
                if outcome == 'good' and (results_type == 'goodqc_validated' or results_type == 'warningqc_validated' or results_type == 'resequencing_validated'):
                    MainMongo(pseudo_id, self._species, results_type, subvaldict=validation_dict, connection_string='CONNECTION_STRING_AZURE')
                    self.__export_json_results(self._isolates_collection, isolatename, pseudo_id, 'accepted')
                else:
                    collection = self._isolates_resequencing_collection if resequencing == 'yes' else \
                        self._isolates_warningqc_collection if quality == 'warning' else self._isolates_goodqc_collection
                    self.__export_json_results(collection, isolatename, pseudo_id, 'rejected')
                    self.__remove_id_from_document_to_be_unique_again_if_bad(collection, pseudo_id, validation_dict)

    @staticmethod
    def __get_results_type(quality: str, resequencing: bool) -> str:
        """
        Gets the corresponding results_type in MongoDB with the given validation_type from BIGSdb.
        :param quality: str, either good or bad
        :param resequencing: boolean, whether it is a resequencing or not
        :return: results_type, either goodqc_validated, warningqc_validated or resequencing_validated
        """
        if resequencing == 'yes':
            results_type = 'resequencing_validated'
        elif quality == 'good':
            results_type = 'goodqc_validated'
        elif quality == 'warning':
            results_type = 'warningqc_validated'
        else:
            results_type = '?'  # in order to not have issue 'variable referenced before assignment' and in order to leave possibility open
        return results_type


    @staticmethod
    def __remove_id_from_document_to_be_unique_again_if_bad(collection_in: Collection,
                                                            isolatename: str, validation_dict: Dict[str, str]) -> None:
        """
        This function modifies the document to not have the unique bioit identifier anymore, but the MongoDB
        autogenerated one. Apparently the only or easiest way to do this is to reinsert the document.
        The goal of this manipulation is to be able to insert new resequencings, good samples or samples with a quality
        warning. Additionally, it adds the validation dict.
        :param collection_in: collection document is in
        :param isolatename: name of the isolate
        :param validation_dict: dictionary containing the validation metadata
        :return: None
        """
        negatively_validated_document = dict(
            collection_in.with_options(read_concern=ReadConcern(level="majority")).find_one(
                {'_id': isolatename}))
        negatively_validated_document['validation'] = validation_dict
        negatively_validated_document.pop('_id')
        collection_in.with_options(write_concern=WriteConcern(w="majority")).insert_one(
            negatively_validated_document)  # Modified doc
        collection_in.with_options(write_concern=WriteConcern(w="majority")).delete_one(
            {'_id': isolatename})  # Unmodified doc

    @staticmethod
    def __export_json_results(collection: Collection, isolate_id: str, pseudo_id, subfolder: str) -> None:
        """
        Exports the results as a JSON file to a specific location on the NRC platform.
        :param collection: in which the collection the results are located
        :param isolate_id: id of the isolate
        :param pseudo_id: pseudo id of the isolate
        :param subfolder: in which subfolder the reports have to be created
        :return: None
        """
        bigsdb_config_data = get_bigsdb_config_data()
        json_reports_dir = bigsdb_config_data.get('json_reports_dir')
        path = Path(json_reports_dir) / subfolder / f'{isolate_id}.json'
        json_results = MongoRecordDict(collection.find_one({'_id': pseudo_id})).get_json_results()
        json_results['sample'] = json_results['sample'].replace(pseudo_id, isolate_id)
        json_results['input_files'] = json_results['input_files'].replace(pseudo_id, isolate_id)
        json_results.pop('isolates_id')
        json_results.dump_to_json_file(path)


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))
    species = re.sub('bigsdb_|_isolates', '', args.db) if args.db else args.species

    # run main
    SampleValidationToMongo(species, args.sub_id)
