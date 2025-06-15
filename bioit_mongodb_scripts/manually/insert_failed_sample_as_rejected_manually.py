#!/usr/bin/env python
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Union, Any

# import dnspython
# somehow this package is a requirement without actually needing to be imported, probably imported in pymongo

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_insertion import insert_document_into_rejected_collection
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_message import AzureServiceBusMessage

REJECTION_REASONS = {
    "1": "Insufficient reads remaining after human read scrubbing to generate an assembly or consensus sequence.",
    "2": "Insufficient reads remaining after read trimming to generate an assembly or consensus sequence.",
    "3": "Input forward and reverse reads do not match.",
    "4": "Insufficient contigs left after human read scrubbing to execute the pipeline.",
    "5": "One or more input files were corrupted."
}


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str, choices=MongoConfigProvider.get_all_species())
    parser.add_argument("--technical_id", required=True, type=str)
    parser.add_argument("--rejection_reason", required=True, type=str, choices=REJECTION_REASONS.keys(), help="\t".join([f"{k}: {v}" for k, v in REJECTION_REASONS.items()]))
    parser.add_argument('--alternate_dtap', choices=['dev', 'test', 'acc', 'prod'])
    return parser.parse_args()


def insert_failed_sample_as_rejected_manually(technical_id: str, species: str,
                                              rejection_reason: Literal[REJECTION_REASONS.values()],
                                              mongo_config_data: dict[str, Any],
                                              alternate_dtap: Union[str, None] = None) -> None:
    """
    Insert an isolate into the rejected isolates MongoDB Azure collection with a given rejection reason and sends
    a message to the Azure Service Bus.
    :param technical_id: sample id/ isolates id
    :param species: commonly used bioit species name: either genus or specific like stec
    :param rejection_reason: The reason why the sample failed/has to be rejected.
    :param mongo_config_data: The MongoDB configuration data
    :param alternate_dtap: alternative dtap than what is in the config file
    :return: None
    """
    mongo_config_provider = MongoConfigProvider(alternate_dtap=alternate_dtap)
    mongoinit = MongoInitialisation(species,mongo_config_provider.get_azure_connection_string(species), mongo_config_provider.dtap)

    isolates_rejected_coreqc_collection = mongoinit.initialise_isolates_rejected_coreqc_collection()

    document_to_be_inserted = {"_id": technical_id,
                               "rejection_reasons": {'manual': rejection_reason},
                               "creation_date": datetime.now(timezone.utc),
                               "insertion_type": 'manual'}

    insert_document_into_rejected_collection(isolates_rejected_coreqc_collection, document_to_be_inserted)

    asb_instance = AzureServiceBus(mongo_config_data, species, alternate_dtap)
    asb_instance.send_message_to_queue(AzureServiceBusMessage(technical_id, isolates_rejected_coreqc_collection.name))


if __name__ == '__main__':
    # Parse arguments
    args = parse_arguments()

    # run main
    insert_failed_sample_as_rejected_manually(args.technical_id,
                                              args.species,
                                              REJECTION_REASONS[args.rejection_reason],
                                              args.alternate_dtap)
