import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path


PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblIsolates
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import send_email

logger = logging.getLogger(__name__)

def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=MongoConfigProvider.get_currently_supported_species())
    return argument_parser.parse_args()


class MongoToBigsNominative:
    """
    Initializing this class will trigger its main function.
    If the current host is a bigsdb host, inserts all nominative metadata for all samples in the bigsdb database that
    do not have their nominative metadata inserted yet.
    """
    def __init__(self, species: str, mongo_config_provider: MongoConfigProvider, dont_send_email: bool = False) -> None:
        """
        Initializes this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param mongo_config_provider: the mongodb configuration provider.
        :param dont_send_email: do not send emails, only log
        :return: None
        """

        self._species = species
        self._dont_send_email = dont_send_email

        # Open collections local MongoDB
        self._mongoinit_local = MongoInitialisation(self._species, mongo_config_provider.get_local_connection_string(self._species), mongo_config_provider.dtap)
        self._nominative_labtest_clinical_metadata_collection = self._mongoinit_local.initialise_nominative_labtest_clinical_metadata_collection()
        self._mappingtable_collection = self._mongoinit_local.initialise_mapping_table_collection()

        try:
            self._mongo_to_bigs_nominative()
        except Exception as exceptionmessage:
            logger.error(f"Fail on host {socket.gethostname()}: {exceptionmessage}\n{traceback.format_exc()}")
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: {exceptionmessage}\n{traceback.format_exc()}")

    def _mongo_to_bigs_nominative(self) -> None:
        """
        Main function
        If the current host is a bigsdb host, inserts all nominative metadata for all samples in the bigsdb database
        that do not have their nominative metadata inserted yet.
        :return: None
        """
        list_of_documents = list(self._nominative_labtest_clinical_metadata_collection.
                                 find({'inserted_into_bigsdb': {'$ne': True}, 'CLIN_received': True,
                                       'LAB_received': True}))

        for document in list_of_documents:
            mapping_table = self._mappingtable_collection.find_one({'_id': document['sample_id']})
            if not mapping_table:
                continue
            with TblIsolates(self._species) as isolates_psql_tbl:
                sample_presence = isolates_psql_tbl.count_isolate((mapping_table['_id'],))
                dict_to_be_inserted = {}
                if sample_presence[0][0] != 0:  # only add metadata if sample exists in bigsdb
                    for key, value in document.items():
                        if key not in ['inserted_into_bigsdb', '_id', 'sample_id', 'LAB_received', 'CLIN_received'] and value is not None:
                            dict_to_be_inserted[key] = value
                    isolate_update_query = isolates_psql_tbl.build_update_nomin_metadata_query(dict_to_be_inserted)
                    values_to_set_in_fields = [v for v in dict_to_be_inserted.values()]
                    values_to_set_in_fields.append(mapping_table['_id'])
                    isolates_psql_tbl.update_nomin_metadata(isolate_update_query, values_to_set_in_fields)
                self._nominative_labtest_clinical_metadata_collection.update_one({'_id': document['_id']},
                                                                                 {'$set': {'inserted_into_bigsdb': True}})


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    args = parse_arguments()
    mongo_config_provider = MongoConfigProvider()

    # run main
    MongoToBigsNominative(args.species, mongo_config_provider)
