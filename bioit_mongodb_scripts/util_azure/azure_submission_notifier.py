import argparse
import socket
import traceback

from bioit_bigsdb_scripts.components.psql import TblFailedInsertions
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.python_utility_functions import send_email
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_submission_message import AzureServiceBusSubmissionMessage


def parse_arguments(specieslist: list[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', type=str, choices=specieslist, required=True)
    return argument_parser.parse_args()


def notify_submissions_in_azure_service_bus(species: str) -> None:
    """
    Sends a notification message to the Azure Service Bus.
    :param species: The species for which submissions are to be notified.
    :return: None
    """
    mongo_config_provider = MongoConfigProvider()
    azure_service_bus = AzureServiceBus(mongo_config_provider, species)
    message = AzureServiceBusSubmissionMessage(species)
    azure_service_bus.send_message_to_submission_queue(message)


if __name__ == '__main__':

    args = parse_arguments(MongoConfigProvider.get_currently_supported_species())

    try:
        notify_submissions_in_azure_service_bus(args.species)
    except Exception as e:
        with TblFailedInsertions(args.species) as failed_insertion_psql_tbl:
            failed_insertion_psql_tbl.insert_batch_submission_failure(('failed notification of batch validation', str(e)))
        host = socket.gethostname()
        send_email(f"Batch validation done but no message sent to the Service bus on {host}\n{traceback.format_exc()}", subject=f'Batch validation notification failure on {host}')
        raise e
