import json
from typing import Any, Union

from bson import ObjectId


# Custom JSON encoder that knows how to handle ObjectId
class JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that knows how to handle ObjectId
    """
    def default(self, obj: Any) -> Union[str, Any]:
        """
        Overrides the default method to handle ObjectId instances. If obj is an instance of ObjectId, it is converted
        to a string. Otherwise, the default method from the parent class is used to handle the obj.
        param obj: object
        :return: string when the object is of type ObjectID or any type that the base class would return
        """
        if isinstance(obj, ObjectId):
            return str(obj)
        return json.JSONEncoder.default(self, obj)
