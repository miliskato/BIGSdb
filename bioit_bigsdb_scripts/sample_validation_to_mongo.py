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

import pymongo
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSubmissions
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_mongodb_scripts.mainmongo import MainMongo
from bioit_mongodb_scripts.mongo_to_bigs import MongoToBigs
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation


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
    from the resequencing or badqc collection to the isolates collection.
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
        self._mongoinit = MongoInitialisation(self._species)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, self._isolates_resequencing_collection = self._mongoinit.initialise_collections()

        # Run main
        try:
            self._sample_validation_to_mongo()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name} fail on host {socket.gethostname()}")
            raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")

    def _sample_validation_to_mongo(self) -> None:
        """
        This scripts runs when a sample has been validated on BIGSdb by a curator. Main steps:
        1) The validation outcome is added into the results of the samples (curator name and outcome).
        2) If the outcome is 'good', the script mainmongo.py is called in with specific options (see below).
        In this mode, the mainmongo will retrieve the sample to insert in the isolate collection. It will also
        add the date of validation (which can't be passed though the json as the date object is not serializable).
        In addition, path to fasta and vcffile are also added.
        If the outcome is bad, the date is added to the dict of the validation outcome and this dict is saved into the
        results of the badqc_isolates
        :return: None
        """
        # Connect to db and create cursor
        with TblSubmissions(self._species) as self._isolates_submissions_psql_tbl:
            query: List[Tuple[Any]] = self._isolates_submissions_psql_tbl.select_closed_submission((self._sub_id,))
            if query:
                # retrieve id of the isolate and curator id from BIGSdb
                isolatename: str = query[0][0]
                outcome: str = query[0][1]
                curator_mailadress: str = query[0][2]
                validation_type: str = query[0][3]
                results_type = self.__get_results_type(validation_type)
                # GO into mongo DB
                validation_dict = {
                    'outcome': outcome,
                    'curator': curator_mailadress,
                    'type': results_type.split('_')[0],
                    'date': datetime.datetime.utcnow().strftime('%d/%m/%Y - %X')
                }
                if outcome == 'good':
                    MainMongo(isolatename, self._species, results_type, subvaldict=validation_dict)
                else:  # outcome == 'bad'
                    if validation_type == 'bad_quality':
                        self.__remove_id_from_document_to_be_unique_again_if_bad(self._isolates_badqc_collection,
                                                                                 isolatename, validation_dict)
                    elif validation_type == 'resequencing':
                        self.__remove_id_from_document_to_be_unique_again_if_bad(self._isolates_resequencing_collection,
                                                                                 isolatename, validation_dict)
                # update status once everything is finished
                self._isolates_submissions_psql_tbl.update_submission((str(self._sub_id),))
        MongoToBigs(self._species, single_sample_id=isolatename)

    @staticmethod
    def __get_results_type(validation_type: str) -> str:
        """
        Gets the corresponding results_type in MongoDB with the given validation_type from Bigsdb
        :param validation_type: Bigsdb validation type: bad_quality or resequencing
        :return: results_type, either badqc_valdiated or resequencing_validated
        """
        if validation_type == 'bad_quality':
            results_type = 'badqc_validated'
        elif validation_type == 'resequencing':
            results_type = 'resequencing_validated'
        else:
            results_type = '?'  # in order to not have issue 'variable referenced before assignment' and in order to leave possibility open
        return results_type

    @staticmethod
    def __remove_id_from_document_to_be_unique_again_if_bad(collection_in: pymongo.collection.Collection,
                                                            isolatename: str, validation_dict: Dict[str, str]) -> None:
        """
        This function modifies the document to not have the unique bioit identifier anymore, but the MongoDB autogenerated one.
        Appearently the only or easiest way to do this is to reinsert the document.
        The goal of this manipulation is to be able to insert new resequencings or bad samples.
        Additionally it adds the validation dict
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


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))
    species = re.sub('bigsdb_|_isolates', '', args.db) if args.db else args.species

    # run main
    SampleValidationToMongo(species, args.sub_id)
