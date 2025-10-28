import json
from datetime import datetime


class AzureServiceBusSubmissionMessage:
    """
    This class contains methods to handle a single Azure service bus message.
    """

    def __init__(self, species: str):
        """
        This method initialises this class
        :param species: the species for which a submission was processed by batch
        """
        self.species = species
        self.time = f'{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}'

    def to_json(self) -> str:
        """
        Dumps the class variables as JSON.
        :return: class variables as JSON as str.
        """
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls, json_str: str) -> 'AzureServiceBusSubmissionMessage':
        """
        Loads an AzureServiceBusMessage from JSON.
        :param json_str: class variables as JSON as str.
        :return: AzureServiceBusMessage instance
        """
        data = json.loads(json_str)
        return cls(**data)
