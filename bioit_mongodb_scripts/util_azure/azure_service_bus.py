from azure.servicebus import ServiceBusClient, ServiceBusMessage

from .azure_service_bus_message import AzureServiceBusMessage
from ..util.mongo_config_provider import MongoConfigProvider


class AzureServiceBus:
    """
    This class contains methods pertaining to Azure service bus.
    """
    def __init__(self, mongo_config_provider: MongoConfigProvider, species: str) -> None:
        """
        This function initializes the class.
        :param mongo_config_provider: the mongodb configuration provider
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: None
        """
        self._species = species
        self._connection_string_asb = mongo_config_provider.asb_connection_string
        self._dtap = mongo_config_provider.dtap
        self._queue_name = f"{species}_{self._dtap}"
        self._mongo_config_provider = mongo_config_provider

    def send_message_to_queue(self, message: AzureServiceBusMessage) -> None:
        """"
        Function to send a message to its queue in the Azure service bus instance defined in the
        mongo_config_data.
        :param message: message to send to queue
        :return: None
        """
        with ServiceBusClient.from_connection_string(conn_str=self._connection_string_asb, logging_enable=True) as service_bus_client:
            with service_bus_client.get_queue_sender(queue_name=self._queue_name) as sender:
                sender.send_messages(ServiceBusMessage(message.to_json()))
