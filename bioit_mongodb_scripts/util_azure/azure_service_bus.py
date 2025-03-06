from typing import Any, Optional

from azure.servicebus import ServiceBusClient, ServiceBusMessage

from .azure_service_bus_message import AzureServiceBusMessage


class AzureServiceBus:
    """
    This class contains methods pertaining to Azure service bus.
    """
    def __init__(self, mongo_config_data: dict[str, Any], species: str, alternate_dtap: Optional[str] = None) -> None:
        """
        This function initialises the class.
        :param mongo_config_data: The mongodb configuration data
        :param species: commonly used bioit species name: either genus or specific like stec
        :param alternate_dtap: alternative dtap than what is in the config file
        :return: None
        """
        self._mongo_config_data = mongo_config_data
        self._dtap = alternate_dtap if alternate_dtap else self._mongo_config_data['dtap']
        self._queue_name = f"{species}_{self._dtap}"

    def send_message_to_queue(self, message: AzureServiceBusMessage) -> None:
        """"
        Function to send a message to its queue in the Azure service bus instance defined in the
        mongo_config_data.
        :param message: message to send to queue
        :return: None
        """
        with ServiceBusClient.from_connection_string(conn_str=self._mongo_config_data['CONNECTION_STRING_ASB'], logging_enable=True) as service_bus_client:
        	with service_bus_client.get_queue_sender(queue_name=self._queue_name) as sender:
            	sender.send_messages(ServiceBusMessage(message.to_json()))
