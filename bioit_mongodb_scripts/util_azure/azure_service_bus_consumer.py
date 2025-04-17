import argparse
import logging
import signal
import socket
from logging import handlers
from typing import Any, List

from azure.servicebus import ServiceBusClient, ServiceBusReceivedMessage
from pymongo.errors import ConnectionFailure, OperationFailure
from tenacity import RetryCallState, retry, wait_exponential

from bioit_bigsdb_scripts.components.psql import TblFailedInsertions
from bioit_mongodb_scripts.mongo_to_bigs import MongoToBigs
from bioit_mongodb_scripts.update_bigsdb_seqdef import UpdateBIGSdbSeqDef
from bioit_mongodb_scripts.util.error import BadCollectionError, IsolateNotFoundException
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email
from bioit_mongodb_scripts.util.sample_to_validation_bigs import SampleToValidationBigs
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_message import AzureServiceBusMessage

mail_sent = False
# Configure stdout logging
logger = logging.getLogger('bigsdb_insertion')
logger.setLevel(logging.INFO)
handler = handlers.TimedRotatingFileHandler('/var/log/bigsdb_insertions.log', when="D", interval=1, backupCount=14)
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    argument_parser.add_argument('--uploader_mail_address', required=True, type=str)
    return argument_parser.parse_args()


class Cancellation:
    """
    Class to define the cancellation token
    """

    def __init__(self):
        """
        initializes the token to false
        """
        self.cancelled = False

    def cancel(self) -> None:
        """
        Turns the cancellation token to True
        :return: None
        """
        self.cancelled = True


class MessageConsumerDataInserter(AzureServiceBus):
    """
    Checks for messages in Azure service bus and inserts pending isolates in BIGSdb
    """

    def __init__(self, ct: Cancellation, species: str, mongo_config_data_arg: dict[str, Any],
                 uploader_mail_address: str) -> None:
        """
        Method to initialize the class
        :param ct: Cancellation status: need to exit gracefully if something happens on the VM
        :param species: Species name
        :param mongo_config_data_arg: Mongo configuration data
        :param uploader_mail_address: email address of the uploader
        :return: None
        """

        super().__init__(mongo_config_data_arg, species)
        self._ct = ct
        self._uploader_mail_address = uploader_mail_address

    def execute(self) -> None:
        """
        checks for Azure service bus messages and tries to insert the isolates notified in these messages
        :return: None
        """
        global mail_sent
        while not self._ct.cancelled:
            with ServiceBusClient.from_connection_string(conn_str=self._connection_string_asb,
                                                         logging_enable=True) as service_bus_client:
                with service_bus_client.get_queue_receiver(queue_name=self._queue_name) as receiver:
                    update_tool = UpdateBIGSdbSeqDef(self._species)
                    update_tool.update_bigsdb_psql_if_needed()
                    should_update_cache = False
                    received_msgs = receiver.receive_messages(max_wait_time=5, max_message_count=1)

                    while len(received_msgs) > 0:

                        msg = received_msgs[0]
                        if self._ct.cancelled:
                            break
                        received_msgs.clear()
                        pseudo_id = AzureServiceBusMessage.from_json(str(msg)).pseudo_id
                        collection_name = AzureServiceBusMessage.from_json(str(msg)).collection
                        try:
                            self.__insert_new_message_in_postgres(msg, pseudo_id)
                            receiver.complete_message(msg)

                            isolate_id = self._get_isolate_id(self._species, pseudo_id)
                            bigs_db_was_modified = self.__insert_known_isolate(collection_name, isolate_id, msg)
                            self.__rm_msg_from_postgres(msg)
                            if not should_update_cache:
                                should_update_cache = bigs_db_was_modified
                        except ConnectionFailure as e:
                            raise e
                        except OperationFailure as e:
                            raise e
                        except IsolateNotFoundException as e:
                            self.__keep_error_in_postgres(e, msg)
                            raise e
                        except BadCollectionError as e:
                            self.__keep_error_in_postgres(e, msg)
                            raise e
                        except Exception as e:
                            logger.error(e)
                            self.__keep_error_in_postgres(e, msg)
                            raise e

                        if mail_sent:
                            mail_sent = False
                            send_email(f'Service restart on success', f'RESTART: azure_service_bus_consumer restarts on {socket.gethostname()}')
                            logger.info("System restarts on success")

                        received_msgs = receiver.receive_messages(max_wait_time=20, max_message_count=1)

                        if should_update_cache and not received_msgs:
                            try:
                                mongo_to_bigs_instance = MongoToBigs(self._species, self._uploader_mail_address)
                                mongo_to_bigs_instance.cache_and_clustering_update()
                            except Exception as e:
                                raise e

    def __insert_known_isolate(self, collection_name: str, isolate_id: str, msg: ServiceBusReceivedMessage) -> bool:
        """
        inserts isolate for which an isolate_id is known
        :param collection_name: MongoDB collection to which belongs the isolates
        :isolate_id: Isolate ID
        :param msg: a ServiceBusReceivedMessage object
        :return: True if the insertion leads to some changes in BIGSdb else False
        """
        if collection_name == 'isolates_badqc':
            SampleToValidationBigs(self._species, isolate_id, mongo_config_data=self._mongo_config_data)
            return False
        elif collection_name == 'isolates':
            return self.__mongo_to_bigs_insertion(isolate_id, msg)
        else:
            raise BadCollectionError()

    def __keep_error_in_postgres(self, e: Exception, msg: ServiceBusReceivedMessage) -> None:
        """
        keeps track of the exception in postgres db and also in the /var/log/bigsdb_insertion.log
        :param e: Exception
        :param msg: a ServiceBusReceivedMessage object
        :return: None
        """
        template = "An exception of type {0} occurred. Error: {1}"
        exception_msg = template.format(type(e).__name__, e.args[0])
        self.__add_exception_to_msg(msg, exception_msg)

    def __insert_new_message_in_postgres(self, msg: ServiceBusReceivedMessage, pseudo_id: str) -> None:
        """
        inserts a message in table failed_insertions from the isolates db.
        :param msg: a ServiceBusReceivedMessage object
        :param pseudo_id: the pseudo id of the isolate as found in the msg
        :return: None
        """
        with TblFailedInsertions(self._species) as psql_tbl_failed_insertions:
            psql_tbl_failed_insertions.insert_message_id((msg.message_id, pseudo_id))

    def __add_exception_to_msg(self, msg: ServiceBusReceivedMessage, exception_msg: str) -> None:
        """
        updates details stored in the table failed_insertions for this message to keep track of the exception
        :param msg: a ServiceBusReceivedMessage object
        :param exception_msg: the exception message
        :return: None
        """
        with TblFailedInsertions(self._species) as psql_tbl_failed_insertions:
            psql_tbl_failed_insertions.insert_exception_for_message_id((exception_msg, msg.message_id))

    def __rm_msg_from_postgres(self, msg: ServiceBusReceivedMessage) -> None:
        """
        removes entry for this message from the postgres failed_insertion table.
        :param msg: a ServiceBusReceivedMessage object
        :return: None
        """
        with TblFailedInsertions(self._species) as psql_tbl_failed_insertions:
            psql_tbl_failed_insertions.delete_message_id((msg.message_id,))

    def __mongo_to_bigs_insertion(self, isolate_id: str, msg: ServiceBusReceivedMessage) -> bool:
        """
        tries to insert the isolate coming from isolates collection in BIGSdb
        :param isolate_id: the isolate id of the isolate
        :param msg: a ServiceBusReceivedMessage object
        :return: True if the insertion modifies something in BIGSdb else False
        """
        mongo_to_bigs_instance = MongoToBigs(self._species, self._uploader_mail_address, single_sample_id=isolate_id)
        changes_done_in_bigs = mongo_to_bigs_instance.run_mongo_to_bigs()
        return changes_done_in_bigs

    def _get_isolate_id(self, species: str, pseudo_id: str) -> str:
        """
        tries to return the isolate_id based on the pseudo_id found in message
        :param species: the species name

        """
        mongo_init_local = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                               selected_connection_string='CONNECTION_STRING_LOCAL')
        try:
            mongo_init_local.client.admin.command('ping')
        except ConnectionFailure:
            raise ConnectionFailure("Connection failure with local MongoDB, check status of connection")
        except OperationFailure:
            raise OperationFailure("Operation Failure with local MongoDB, check config parameters")
        mapping_table_collection = mongo_init_local.initialise_mapping_table_collection()
        try:
            isolate_id = mapping_table_collection.find_one({'pseudo_id': pseudo_id}).get('_id')
        except AttributeError:
            raise IsolateNotFoundException(pseudo_id)
        return isolate_id


cancel_token = Cancellation()


def handle_shutdown(signum: int, frame: Any) -> None:
    """
    Handler to act on cancel_token when the signal is received.
    :param signum: int corresponding usually to either SIGINT or SIGTERM
    :param frame: current stack frame
    :return: None
    """
    cancel_token.cancel()


def handling_retry_outcome(retry_state: RetryCallState) -> None:
    """
    Function that will write the errors in the log and also send an email if it fails for the first time
    :param retry_state: RetryCallState from Tenacity
    :return: None
    """
    global mail_sent
    if not mail_sent:
        send_email(f"{retry_state.outcome.exception()}\nLook at the logs on {socket.gethostname()} (/var/log/bigsdb_insertions.log)",
                   f'WARNING: azure_service_bus_consumer raised errors on {socket.gethostname()}')
        mail_sent = True
    logger.error("Tentative number %s failed. Message: %s", retry_state.attempt_number, retry_state.outcome.exception())


@retry(wait=wait_exponential(multiplier=1, min=2, max=600), after=handling_retry_outcome)
def run_application(ct: Cancellation, species: str, mongo_config_data_arg: dict[str, Any], uploader_mail_address: str) -> None:
    """
    a decorator function to try again on Exception before stopping execution, retry after 2,2,4,8... seconds with max of 10 minutes between two attempts.
    There is no condition to stop running the service
    :param ct: a Cancellation object
    :param species: the species name
    :param mongo_config_data_arg: the mongo_config_data
    :param uploader_mail_address: the mail address
    :return: None
    """
    data_inserter = MessageConsumerDataInserter(ct, species, mongo_config_data_arg, uploader_mail_address)
    data_inserter.execute()


if __name__ == '__main__':

    # signal handler will be executed when a SIGINT/SIGTERM signal is received
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Parse Mongo config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    try:
        run_application(cancel_token, args.species, mongo_config_data, args.uploader_mail_address)
    except (SystemExit, KeyboardInterrupt):
        pass
