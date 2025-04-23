#!/usr/bin/env python

import argparse

from bioit_mongodb_scripts.rejected_isolate import RejectedIsolate
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation


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
    mongo_config_provider = MongoConfigProvider()
    args = parse_arguments(mongo_config_provider.get_all_species())
    species = args.species
    mongoinit = MongoInitialisation(species, mongo_config_provider.get_azure_connection_string(species), mongo_config_provider.dtap)

    rejected_isolates_collection = mongoinit.initialise_isolates_rejected_coreqc_collection()
    rejected_isolate_documents = rejected_isolates_collection.find({'inserted_in_bigsdb': {'$exists': False}})
    for rejected_isolate_document in rejected_isolate_documents:
        rejected_isolate = RejectedIsolate(species, rejected_isolate_document['_id'])
        rejected_isolate.insert_in_rejected_isolates_table()
