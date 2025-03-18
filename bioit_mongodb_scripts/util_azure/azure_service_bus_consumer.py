import argparse
import logging
import signal
from typing import Any, List

from azure.servicebus import ServiceBusClient, ServiceBusReceivedMessage, ServiceBusReceiver

from bioit_bigsdb_scripts.components.psql import TblFailedInsertions
from bioit_mongodb_scripts.mongo_to_bigs import MongoToBigs
from bioit_mongodb_scripts.update_bigsdb_seqdef import UpdateBIGSdbSeqDef
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data
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
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class MessageConsumerDataInserter(AzureServiceBus):

    def __init__(self, ct: Cancellation, species: str, mongo_config_data: dict[str, Any], uploader_mail_address: str) -> None:
        """
        Method to initialize the class
        :param ct: Cancellation status: need to exit gracefully if something happens on the VM
        """
        super().__init__(mongo_config_data, species)
        self._ct = ct
        self._uploader_mail_address = uploader_mail_address
        self._species = species


    def execute(self) -> None:
        with (ServiceBusClient.from_connection_string(conn_str=self._connection_string_asb, logging_enable=True) as service_bus_client):
            with service_bus_client.get_queue_receiver(queue_name=self._queue_name) as receiver:

                while not self._ct.cancelled:
                    update_tool = UpdateBIGSdbSeqDef(self._species)
                    update_tool.update_bigsdb_psql_if_needed()
                    need_to_run_cache = False
                    received_msgs = receiver.receive_messages(max_wait_time=5, max_message_count=1)

                    while len(received_msgs) > 0:
                        msg = received_msgs[0]
                        if self._ct.cancelled:
                            break
                        pseudo_id = AzureServiceBusMessage.from_json(str(msg)).pseudo_id
                        collection = AzureServiceBusMessage.from_json(str(msg)).collection
                        self.__insert_new_message_in_postgres(msg, pseudo_id)
                        receiver.complete_message(msg)
                        isolate_id = self._try_return_isolate_identifier(msg, pseudo_id, receiver)

                        ######✨✨✨✨✨✨🎨🎨🎨🎨🧦🧦🧦 would like to use method but how to change need_to_run_cache
                        if isolate_id and collection == 'isolates_badqc':
                            SamplesToValidationBigs(self._species, mongo_config_data=self._mongo_config_data)

                        elif isolate_id and collection == 'isolates':
                            change_done_in_bigs = self._try_mongo_to_bigs_insertion(isolate_id, msg)
                            self._rm_msg_from_postgres(msg)
                            if not need_to_run_cache:
                                need_to_run_cache = change_done_in_bigs
                        received_msgs.clear()
                        received_msgs = receiver.receive_messages(max_wait_time=5, max_message_count=1)

                    if need_to_run_cache and not received_msgs :
                        mongo_to_bigs_instance = MongoToBigs(self._species, self._uploader_mail_address)
                        mongo_to_bigs_instance.cache_and_clustering_update()

    def __insert_new_message_in_postgres(self, msg: ServiceBusReceivedMessage, pseudo_id: str) -> None:
        """
        insert a message in table Failed
        """
        with TblFailedInsertions(self._species) as psql_tbl_failed_insertions:
            psql_tbl_failed_insertions.insert_message_id((msg.message_id, pseudo_id))

    def _add_exception_to_msg(self, msg: ServiceBusReceivedMessage, exception_msg: str) -> None:
        with TblFailedInsertions(self._species) as psql_tbl_failed_insertions:
            psql_tbl_failed_insertions.insert_exception_for_message_id((exception_msg, msg.message_id))

    def _rm_msg_from_postgres(self, msg: ServiceBusReceivedMessage) -> None:
        with TblFailedInsertions(self._species) as psql_tbl_failed_insertions:
            psql_tbl_failed_insertions.delete_message_id((msg.message_id,))

    def _try_mongo_to_bigs_insertion(self, isolate_id, msg):
        changes_done_in_bigs = False
        try:
            mongo_to_bigs_instance = MongoToBigs(self._species, self._uploader_mail_address,
                                                 single_sample_id=isolate_id)
            changes_done_in_bigs = mongo_to_bigs_instance.run_mongo_to_bigs()

        except Exception as e:
            logging.error('%s insertion failed with subsequent error %s', isolate_id, e)
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            exception_msg = template.format(type(e).__name__, e.args)
            self._add_exception_to_msg(msg, exception_msg)

        finally:
            return  changes_done_in_bigs


    def _try_return_isolate_identifier(self, msg: ServiceBusReceivedMessage, pseudo_id:str, receiver: ServiceBusReceiver) -> str | None:
        """
        return the isolate identifier based on the pseudo_id found in message
        :param msg: one message from the list of ServiceBusReceivedMessage
        :param receiver: ServiceBusReceiver
        """
        try:
            isolate_id = self._get_isolate_identifier(self._species, pseudo_id)
            return isolate_id

        except Exception as e:
            logging.error('%s did not get isolate_id from query on mapping collection: %s', pseudo_id, e)
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            exception_msg = template.format(type(e).__name__, e.args)
            self._add_exception_to_msg(msg, exception_msg)



    def _get_isolate_identifier(self, species: str, pseudo_id: str) -> str:
        mongo_init_local = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                               selected_connection_string='CONNECTION_STRING_LOCAL')
        mapping_table_collection = mongo_init_local.initialise_mapping_table_collection()
        isolate_id = mapping_table_collection.find_one({'pseudo_id': pseudo_id})['_id']
        return isolate_id

cancel_token = Cancellation()
def handle_shutdown(signum:int, frame: Any):
    cancel_token.cancel()

if __name__ == '__main__':

    # signal handler will be executed when a SIGINT/SIGTERM signal is received
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Configure stdout logging
    logging.basicConfig(level=logging.WARNING, filename='/var/log/bigsdb_insertions.log', filemode='w',)

    # Parse Mongo config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])
    try:
        data_inserter = MessageConsumerDataInserter(cancel_token, args.species, mongo_config_data, args.uploader_mail_address)
        data_inserter.execute()
    except (SystemExit, KeyboardInterrupt):
        pass
