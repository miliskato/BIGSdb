import json
from typing import Type, TypeVar

# declare a generic type variable T restricted to subclasses of AzureMessageBase
T = TypeVar('T', bound='AzureMessageBase')


class AzureMessageBase:
    """
    Base class with methods to handle the creation and the reading of messages for the Azure service bus.
    Subclasses must define an __init__ compatible with the stored attributes.
    """
    def to_json(self) -> str:
        """
        Dumps the class variables as JSON.
        :return: class variables as JSON as str.
        """
        return json.dumps(self.__dict__)

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """
        Loads a message from JSON.
        :param json_str: class variables as JSON as str.
        :return: message instance
        """
        data = json.loads(json_str)
        return cls(**data)
