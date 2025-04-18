#!/usr/bin/env python

import argparse

from bioit_mongodb_scripts.rejected_isolate import RejectedIsolate
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


def parse_arguments(specieslist: list[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


if __name__ == '__main__':
    # TODO this script should be replaced by the AzureServiceBus
    mongo_config_data = get_mongodb_config_data()
    args = parse_arguments(mongo_config_data['species'])
    species = args.species
    mongoinit = MongoInitialisation(
        species,
        mongo_config_data=mongo_config_data,
        alternate_dtap=mongo_config_data.get('dtap'),
        selected_connection_string='CONNECTION_STRING_AZURE'
    )
    rejected_isolates_collection = mongoinit.initialise_isolates_rejected_coreqc_collection()
    rejected_isolate_documents = rejected_isolates_collection.find({'inserted_in_bigsdb': {'$exists': False}})
    for rejected_isolate_document in rejected_isolate_documents:
        rejected_isolate = RejectedIsolate(species, rejected_isolate_document['_id'])
        rejected_isolate.insert_in_rejected_isolates_table()
