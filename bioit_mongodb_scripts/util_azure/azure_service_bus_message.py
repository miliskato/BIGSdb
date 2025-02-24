import json


class AzureServiceBusMessage:
    """
    This class contains methods to handle a single Azure service bus message.
    """
    def __init__(self, pseudo_id: str, collection: str):
        """
        This method initialises this class
        :param pseudo_id: the pseudo id of the isolate
        :param collection: the collection that the isolate has been inserted in
        """
        self.pseudo_id = pseudo_id
        self.collection = collection

    def to_json(self) -> str:
        """
        Dumps the class variables as JSON.
        :return: class variables as JSON as str.
        """
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_str: str) -> 'AzureServiceBusMessage':
        """
        Loads an AzureServiceBusMessage from JSON.
        :param json_str: class variables as JSON as str.
        :return: AzureServiceBusMessage instance
        """
        data = json.loads(json_str)
        return cls(**data)
