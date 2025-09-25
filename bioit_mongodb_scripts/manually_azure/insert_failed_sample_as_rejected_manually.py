#!/usr/bin/env python
import argparse
import socket
import sys

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Union

# import dnspython
# somehow this package is a requirement without actually needing to be imported, probably imported in pymongo

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_insertion import insert_document_into_rejected_collection
from bioit_mongodb_scripts.util.python_utility_functions import execute_command
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_message import AzureServiceBusMessage
from bioit_mongodb_scripts.util_azure.connect_azure import ConnectAzure

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
    parser.add_argument("--species", required=True, type=str, choices=MongoConfigProvider.get_currently_supported_species())
    parser.add_argument("--technical_id", required=True, type=str)
    parser.add_argument("--rejection_reason", required=True, type=str, choices=REJECTION_REASONS.keys(), help="\t".join([f"{k}: {v}" for k, v in REJECTION_REASONS.items()]))
    parser.add_argument('--alternate_dtap', choices=['dev', 'test', 'acc', 'prod'])
    parser.add_argument('--disable_archival', required=False, action='store_true')
    return parser.parse_args()


def insert_failed_sample_as_rejected_manually(technical_id: str, species: str,
                                              rejection_reason: Literal[REJECTION_REASONS.values()],
                                              alternate_dtap: Union[str, None] = None,
                                              disable_archival: bool = False) -> None:
    """
    Insert an isolate into the rejected isolates MongoDB Azure collection with a given rejection reason and sends
    a message to the Azure Service Bus.
    :param technical_id: sample id/ isolates id
    :param species: commonly used bioit species name: either genus or specific like stec
    :param rejection_reason: The reason why the sample failed/has to be rejected.
    :param alternate_dtap: alternative dtap than what is in the config file
    :param disable_archival: whether the archival should be disabled.
    :return: None
    """
    mongo_config_provider = MongoConfigProvider(alternate_dtap=alternate_dtap)
    mongoinit = MongoInitialisation(species, mongo_config_provider.get_azure_connection_string(species), mongo_config_provider.dtap)

    isolates_rejected_coreqc_collection = mongoinit.initialise_isolates_rejected_coreqc_collection()

    document_to_be_inserted = {"_id": technical_id,
                               "rejection_reasons": {'manual': rejection_reason},
                               "creation_date": datetime.now(timezone.utc),
                               "insertion_type": 'manual'}

    insert_document_into_rejected_collection(isolates_rejected_coreqc_collection, document_to_be_inserted)

    asb_instance = AzureServiceBus(mongo_config_provider, species)
    asb_instance.send_message_to_queue(AzureServiceBusMessage(technical_id, isolates_rejected_coreqc_collection.name))

    if disable_archival:
        return
    else:
        _execute_archival(mongo_config_provider.dtap, species, technical_id)


def _execute_archival(dtap: str, species: str, technical_id: str) -> None:
    """
    Executes the original archival copy command from the most recent task of the given technical_id if it can find it.
    :param dtap: current dtap
    :param species: current species
    :param technical_id: current technical_id
    :return: None
    """
    # Find most recent task with technical_id
    connection_azure = ConnectAzure(dtap)
    batch_client = connection_azure.connect_to_batch_client()
    matching_tasks = []

    # Loop over all jobs because there are multiple possibilities
    for job in batch_client.job.list():
        if species not in job.id or 'reanalysis' in job.id:
            continue
        # Step 2: list tasks for this job
        for task in batch_client.task.list(job.id):
            if task.id.startswith(technical_id):
                matching_tasks.append(task)

    # Get most recent task by ID
    latest_task = max(matching_tasks, key=lambda t: t.id)

    # Extract archival command
    _, _, archival_copy_cmd = latest_task.command_line.partition("module load azcopy")
    if not archival_copy_cmd:
        raise RuntimeError(f"No 'module load azcopy' found in command for task {latest_task.id}")

    archival_command = "module load azcopy" + archival_copy_cmd.rstrip('"')

    # Execute archival command
    execute_command(archival_command)


if __name__ == '__main__':
    # Parse arguments
    args = parse_arguments()

    # Check that script is not invoked locally
    if 'bioit' in socket.gethostname() and not args.disable_archival:
        raise Exception('This script should be run on a corresponding (dt or ap) Azure VM with a managed identity '
                        '(e.g. reportsapi VM). If it really must be executed locally, please use the disable_archival'
                        'flag and understand that the input files will not be archived automatically')

    # run main
    insert_failed_sample_as_rejected_manually(args.technical_id,
                                              args.species,
                                              REJECTION_REASONS[args.rejection_reason],
                                              args.alternate_dtap,
                                              args.disable_archival)
