import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import List

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblIsolates
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


class MongoToBigsNominative:
    """
    Initializing this class will trigger its main function.
    If the current host is a bigsdb host, inserts all nominative metadata for all samples in the bigsdb database that
    do not have their nominative metadata inserted yet.
    """
    def __init__(self, species: str) -> None:
        """
        Initializes this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        self._species = species

        # Parse MongoDB config
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()

        # Open collections local MongoDB
        self._mongoinit_local = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                                    alternate_connection_string=self._mongo_config_data['CONNECTION_STRING_LOCAL'])  # todo modify to new mongoinit but is not in this branch
        self._nominative_labtest_clinical_metadata_collection = self._mongoinit_local.initialise_nominative_labtest_clinical_metadata_collection()

        # Open Bigsdb isolates table
        self._isolates_psql_tbl = TblIsolates(self._species)

        try:
            self._mongo_to_bigs_nominative()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: {exceptionmessage}\n{traceback.format_exc()}")

    def _mongo_to_bigs_nominative(self) -> None:
        """
        Main function
        If the current host is a bigsdb host, inserts all nominative metadata for all samples in the bigsdb database that
        do not have their nominative metadata inserted yet.
        :return: None
        """
        list_of_documents = list(self._nominative_labtest_clinical_metadata_collection.find({'inserted_into_bigsdb': {'$ne': True}}))

        for document in list_of_documents:
            sample_presence = self._isolates_psql_tbl.count_isolate((document['_id'],))
            dict_to_be_inserted = {}
            if sample_presence[0][0] == 0:
                for key, value in document.items():
                    if key not in ['inserted_into_bigsdb', '_id'] and value is not None:
                        dict_to_be_inserted[key] = value
                species_update_query = TblIsolates.build_update_nomin_metadata_query(dict_to_be_inserted)
                with TblIsolates(self._species) as isolates_psql_tbl:
                    isolates_psql_tbl.update_nomin_metadata(species_update_query, [document['_id']])
                self._nominative_labtest_clinical_metadata_collection.update_one({'_id': document['_id']},
                                                                                 {'$set': {'inserted_into_bigsdb': True}})
        # todo in failsafe set false; either in mongo_to_bigs or in mainmongo; todo after merge with ASG overhaul


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse Mongo config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    MongoToBigsNominative(args.species)
