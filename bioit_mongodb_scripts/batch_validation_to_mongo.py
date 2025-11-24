import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import List, Tuple

from azure.servicebus import ServiceBusClient
from tenacity import RetryCallState, retry, wait_exponential

from bioit_mongodb_scripts.helpers.services_helpers import Cancellation, config_log_handlers
from bioit_bigsdb_scripts.components.psql import TblSubmissions
from bioit_bigsdb_scripts.sample_validation_to_mongo import SampleValidationToMongo
from bioit_mongodb_scripts.util.python_utility_functions import send_email
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_specific_messages import AzureServiceBusSubmissionMessage

mail_sent = False
logger = logging.getLogger(__name__)


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', type=str, choices=specieslist)
    return argument_parser.parse_args()


class BatchValidationToMongo(AzureServiceBus):
    """
    This class handles validation/insertion in mongoDB of isolates already pushed in BIGSdb submissions table.
    """

    def __init__(self, ct: Cancellation, species: str, mongo_config_provider: MongoConfigProvider) -> None:
        """
        Initialises the class and runs the main function
        :param species: commonly used bioit species name.
        :return: None
        """
        super().__init__(mongo_config_provider, species)
        self._species = species
        self._ct = ct

    def execute(self) -> None:
        """
        checks for messages in the submission queue of the azure service bus and process them.
        :return: None
        """
        global mail_sent
        while not self._ct.cancelled:
            logger.debug('Validation service: waiting for messages in the batch validation service bus queue')
            with ServiceBusClient.from_connection_string(conn_str=self._connection_string_asb,
                                                         logging_enable=True) as service_bus_client:
                with service_bus_client.get_queue_receiver(queue_name=self._submissions_queue_name) as receiver:
                    received_msgs = receiver.receive_messages(max_wait_time=5, max_message_count=1)

                    while len(received_msgs) > 0:

                        msg = received_msgs[0]
                        if self._ct.cancelled:
                            break
                        msg_species = AzureServiceBusSubmissionMessage.from_json(str(msg)).species
                        received_msgs.clear()
                        if msg_species != self._species:
                            logger.info(f"Message for species {msg_species} received in {self._species} queue. Ignoring it.")
                            receiver.dead_letter_message(msg, reason="Species mismatch")
                            continue
                        try:
                            self._validate_pending_submission_after_batch_validation()
                            receiver.complete_message(msg)
                        except Exception as exceptionmessage:
                            logger.error(f"Fail on host {socket.gethostname()}: {exceptionmessage}\n{traceback.format_exc()}")
                            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                                       f"{Path(__file__).name} fail on host {socket.gethostname()}")
                            raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")
                        if mail_sent:
                            mail_sent = False
                            send_email(f'Validation service restart on success', f'RESTART: Service for batch validation restarts on {socket.gethostname()}')
                            logger.info("System restarts on success")

                        received_msgs = receiver.receive_messages(max_wait_time=20, max_message_count=1)

    def _validate_pending_submission_after_batch_validation(self) -> None:
        """
        Method to handle submissions that were validated/rejected by batch in BIGSdb.
        The validated submissions (good or bad) will be processed for insertion in BIGSdb.
        :return: None
        """
        validated_submission_ids = get_submission_ids_to_process(self._species)

        for sub_id in validated_submission_ids:
            try:
                SampleValidationToMongo(self._species, sub_id=int(sub_id[0]), batch_validated=True)
            except Exception as e:
                raise Exception(f"Error processing submission ID {sub_id[0]}: {e}")


def get_submission_ids_to_process(species: str) -> List[Tuple[str]]:
    """
    Function to get submission ids that were batch validated in BIGSdb
    :param species: the species name
    :return: list of submission ids
    """
    with TblSubmissions(species=species) as isolates_submissions_psql_tbl:
        return list(isolates_submissions_psql_tbl.get_submission_ids_batch_validated())


def handling_retry_outcome(retry_state: RetryCallState) -> None:
    """
    Function that will write the errors in the log and also send an email if it fails for the first time
    :param retry_state: RetryCallState from Tenacity
    :return: None
    """
    global mail_sent
    if not mail_sent:
        send_email(
            f"{retry_state.outcome.exception()}\nLook at the logs on {socket.gethostname()} (/var/log/bigsdb_batch_validation_service/bigsdb_batch_validation_[species].log)",
            f'WARNING: batch_validation_of_submission raised errors on {socket.gethostname()}')
        mail_sent = True
    logger.error("Tentative number %s failed. Message: %s", retry_state.attempt_number, retry_state.outcome.exception())


@retry(wait=wait_exponential(multiplier=1, min=2, max=600), after=handling_retry_outcome)
def run_application(ct: Cancellation, species: str, mongo_config_provider: MongoConfigProvider) -> None:
    """
    a decorator function to try again on Exception before stopping execution, retry after 2,2,4,8... seconds with max of 10 minutes between two attempts.
    There is no condition to stop running the service
    :param ct: a Cancellation object
    :param species: the species name
    :param mongo_config_provider: the mongo db configuration provider
    :return: None
    """
    batch_validator = BatchValidationToMongo(ct, species, mongo_config_provider)
    batch_validator.execute()


if __name__ == '__main__':

    cancel_token = Cancellation()

    logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

    mongo_config_provider = MongoConfigProvider()
    args = parse_arguments(mongo_config_provider.get_currently_supported_species())
    config_log_handlers(args.species)

    try:
        run_application(cancel_token, args.species, mongo_config_provider)
    except (SystemExit, KeyboardInterrupt):
        pass
