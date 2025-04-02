import argparse
import logging
import signal
import socket
from typing import Any, List

from azure.servicebus import ServiceBusClient, ServiceBusReceivedMessage
from pymongo.errors import ConnectionFailure, OperationFailure
from tenacity import RetryCallState, after_log, retry, stop_after_attempt, wait_fixed

from bioit_bigsdb_scripts.components.psql import TblFailedInsertions
from bioit_mongodb_scripts.mongo_to_bigs import MongoToBigs
from bioit_mongodb_scripts.update_bigsdb_seqdef import UpdateBIGSdbSeqDef
from bioit_mongodb_scripts.util.error import BadCollectionError, IsolateNotFoundException
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email
from bioit_mongodb_scripts.util.samples_to_validation_bigs import SamplesToValidationBigs
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_message import AzureServiceBusMessage


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
        initialized the token to false
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

    def __init__(self, ct: Cancellation, species: str, mongo_config_data: dict[str, Any],
                 uploader_mail_address: str) -> None:
        """
        Method to initialize the class
        :param ct: Cancellation status: need to exit gracefully if something happens on the VM
        :param species: Species name
        :param mongo_config_data: Mongo configuration data
        :return: None
        """

        super().__init__(mongo_config_data, species)
        self._ct = ct
        self._uploader_mail_address = uploader_mail_address
        self._species = species

    def execute(self) -> None:
        """
        checks for Azure service bus message and try to insert the isolates notified in these messages
        :return: None
        """
        while not self._ct.cancelled:
            with (ServiceBusClient.from_connection_string(conn_str=self._connection_string_asb,
                                                          logging_enable=True) as service_bus_client):
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
                            if not should_update_cache:
                                should_update_cache = bigs_db_was_modified
                        except ConnectionFailure:
                            raise ConnectionFailure("Connection Failure with local MongoDB")
                        except OperationFailure:
                            raise OperationFailure("Connection Failure with local MongoDB")
                        except IsolateNotFoundException as e:
                            self.__handle_exception(e, msg)
                        except BadCollectionError as e:
                            self.__handle_exception(e, msg)
                        except Exception as e:
                            send_email(f'{e.args}',
                                       f'MessageConsumerDataInserter failed on {socket.gethostname()}')
                            logging.error(e)
                            self.__handle_exception(e, msg)

                        received_msgs = receiver.receive_messages(max_wait_time=20, max_message_count=1)

                        if should_update_cache and not received_msgs:
                            try:
                                mongo_to_bigs_instance = MongoToBigs(self._species, self._uploader_mail_address)
                                mongo_to_bigs_instance.cache_and_clustering_update()
                            except Exception as e:
                                logging.error('cache update or clustering failed with error: %s', e)
                                send_email(f'{e.args}',
                                           f'MessageConsumerDataInserter failed on {socket.gethostname()}')

    def __insert_known_isolate(self, collection_name: str, isolate_id: str, msg: ServiceBusReceivedMessage) -> bool:
        """ inserts isolates for which an isolate_id is known
        :param collection_name: MongoDB collection to which belongs the isolates
        :isolate_id: Isolate ID
        :param msg: a ServiceBusReceivedMessage object
        """
        if collection_name == 'isolates_badqc':
            SamplesToValidationBigs(self._species, mongo_config_data=self._mongo_config_data)
            return False
        elif collection_name == 'isolates':
            return self.__mongo_to_bigs_insertion(isolate_id, msg)
        else:
            raise BadCollectionError()

    def __handle_exception(self, e: Exception, msg: ServiceBusReceivedMessage) -> None:
        """
        keep track of the exception in postgres db and also in the /var/log/bigsdb_insertion.log
        :param e: Exception
        :param msg: a ServiceBusReceivedMessage object
        """
        logging.error('Insertion failed with subsequent error %s', e)
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
        self.__rm_msg_from_postgres(msg)
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
            raise ConnectionFailure()
        except OperationFailure:
            raise OperationFailure("Connection Failure with local MongoDB")
        mapping_table_collection = mongo_init_local.initialise_mapping_table_collection()
        try:
            isolate_id = mapping_table_collection.find_one({'pseudo_id': pseudo_id}).get('_id')
        except:
            raise IsolateNotFoundException(pseudo_id)
        return isolate_id


cancel_token = Cancellation()


def handle_shutdown(signum: int, frame: Any) -> None:
    """
    Pointer to act on cancel_token when the signal is received.
    :param signum: int corresponding usually to either SIGINT or SIGTERM
    :param frame: current stack frame
    :return: None
    """
    cancel_token.cancel()


def on_error(retry_state: RetryCallState) -> None:
    """
    function to log the error although not catching it
    :param retry_state: RetryCallState object from tenacity
    :return: None
    """
    logging.exception(
        f'{retry_state.outcome.exception()}'
    )
    send_email(f'{retry_state.outcome.exception()}', f'WARNING: azure_service_bus_consumer has stopped on {socket.gethostname()}')
    raise retry_state.retry_object.retry_error_cls(retry_state.outcome) from retry_state.outcome.exception()


@retry(stop=stop_after_attempt(2), wait=wait_fixed(3), after=after_log(logging.getLogger(__name__), logging.WARNING), retry_error_callback=on_error)
def run_application(ct: Cancellation, species: str, mongo_config_data: dict[str, Any], uploader_mail_address: str) -> None:
    """a decorateur function to try again on Exception before stopping execution
    :param ct: a Cancellation object
    :param species: the species name
    :param mongo_config_data: the mongo_config_data
    :param uploader_mail_address: the mail address
    :return: None
    """
    data_inserter = MessageConsumerDataInserter(ct, species, mongo_config_data, uploader_mail_address)
    data_inserter.execute()


if __name__ == '__main__':

    # signal handler will be executed when a SIGINT/SIGTERM signal is received
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Configure stdout logging
    logging.basicConfig(level=logging.WARNING, filename='/var/log/bigsdb_insertions.log', filemode='w', )

    # Parse Mongo config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    try:
        run_application(cancel_token, args.species, mongo_config_data, args.uploader_mail_address)
    except (SystemExit, KeyboardInterrupt):
        pass
