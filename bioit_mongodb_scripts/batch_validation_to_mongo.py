import argparse
import logging
import signal
import socket
import sys
import traceback
from logging import handlers
from pathlib import Path
from typing import List

from azure.servicebus import ServiceBusClient
from tenacity import RetryCallState, retry, wait_exponential

from bioit_mongodb_scripts.helpers.services_helpers import Cancellation, handle_shutdown
from bioit_bigsdb_scripts.components.psql import TblSubmissions
from bioit_bigsdb_scripts.sample_validation_to_mongo import SampleValidationToMongo
from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_submission_message import AzureServiceBusSubmissionMessage

mail_sent = False
logger = logging.getLogger('bigsdb_batch_validation')
logger.setLevel(logging.INFO)


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
    This class handles validation/insertion in mongoDB of warningqcs already pushed in BIGSdb submissions table.
    """

    def __init__(self, ct: Cancellation, species: str, mongo_config_provider: MongoConfigProvider) -> None:
        """
        Initialises the class and runs the main function
        :param species: commonly used bioit species name.
        :return: None
        """
        super().__init__(mongo_config_provider, species)
        self._species = species
        self._submissions_sb_queue = f'{self._queue_name}_submissions'
        self._ct = ct

    def execute(self) -> None:
        """
        checks for messages in the submission queue of the azure service bus and process them.
        :return: None
        """
        while not self._ct.cancelled:
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
        The rejected submissions will be closed and the accepted ones will be processed for insertion in BIGSdb.
        :return: None
        """
        with TblSubmissions(species=self._species) as isolates_submissions_psql_tbl:

            isolates_submissions_psql_tbl.close_batch_rejected_submissions()
            accepted_submission_ids = list(isolates_submissions_psql_tbl.get_submission_ids_batch_validated())

            for sub_id in accepted_submission_ids:
                isolates_submissions_psql_tbl.set_submission_status(('closed', sub_id[0]))
                try:
                    SampleValidationToMongo(self._species, sub_id=int(sub_id[0]))
                except Exception as e:
                    isolates_submissions_psql_tbl.set_submission_status(('failed_insertion', sub_id[0]))
                    raise Exception(f"Error processing submission ID {sub_id[0]}: {e}")


def config_log_handlers(species: str) -> None:
    """
    configure handlers to get logs rotated once by day
    :param species: the species used in ANSIBLE playbook
    :return: None
    """
    handler = handlers.TimedRotatingFileHandler(f'/var/log/bigsdb_batch_validation/bigsdb_batch_validation_{species}.log', when="D", interval=1, backupCount=14)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


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

    # signal handler will be executed when a SIGINT/SIGTERM signal is received
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))
    config_log_handlers(args.species)
    mongo_config_provider = MongoConfigProvider()

    try:
        run_application(cancel_token, args.species, mongo_config_provider, args.uploader_mail_address)
    except (SystemExit, KeyboardInterrupt):
        pass
