import json
from collections import UserDict
from pathlib import Path
from typing import Dict, Any, Literal, Union

ResultType = Literal['new_isolate', 'badqc', 'resequencing', 'reanalysis']


class BridgeDict(UserDict):
    """
    This class is used to get modifications applied to JsonReportDict also
    inherited to the original MongoRecordDict (after use of get_json_results()).
    """
    def __init__(self, source: Dict[str, Any]):
        self.source = source
        super().__init__(source)

    def __setitem__(self, key, item):
        self.source[key] = item
        super().__setitem__(key, item)

    def __delitem__(self, key):
        del self.source[key]
        super().__delitem__(key)


class JsonReportDict(BridgeDict):
    """
    Class to handle results of the pipeline, light typing for code clarity
    Also includes the open method for json file
    """
    @staticmethod
    def from_json(path: Path) -> 'JsonReportDict':
        """
        Opens the json file in a JsonReportDict object
        :param path: path to the json file
        :return: JsonReportDict object
        """
        with path.open('r') as f:
            return JsonReportDict(json.load(f))


class MongoRecordDict(BridgeDict):
    """
    Class to handle documents extracted from MongoDB, light typing for code clarity
    Also includes relevant methods for this object
    """
    def get_id(self) -> str:
        """return the _id field from mongoDB"""
        return self.get('_id')

    def set_isolate_id(self, isolate_id: str) -> None:
        """
        Set the value for the isolates_id key
        :param isolate_id: isolate id
        :return: None
        """
        self['isolates_id'] = isolate_id

    def get_validation_type(self) -> Union[ResultType|None]:
        """return validation type info from Mongo document if present"""
        return self.get('validation',{}).get('type',None)

    def get_json_results(self) -> JsonReportDict:
        """return the results section of the Mongo document as a JsonReportDict object"""
        return JsonReportDict(self.get("results"))
