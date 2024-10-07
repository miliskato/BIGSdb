from collections import UserDict
from pathlib import Path
from typing import Dict, Union, Any, Literal
import json

ResultType = Literal['new_isolate', 'badqc', 'resequencing', 'reanalysis']
"""
Literal type containing the authorized strings for results type definition
"""

class BridgeDict(UserDict):
    """
    This class is used to get modifications applied to JsonReportDict also
    inherited to the original MongoRecordDict (after use of get_json_results()).
    """
    source: Dict[str, Any]

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
    def from_json(path: Union[str, Path]) -> 'JsonReportDict':
        with open(path, 'r') as f:
            return JsonReportDict(json.load(f))


class MongoRecordDict(BridgeDict):
    """
    Class to handle document extracted from MongoDB, light typing for code clarity
    Also includes relevant methods for this object
    """
    def get_id(self) -> str:
        return self.get('_id')

    def set_isolate_id(self, isolate_id: str):
        self['isolates_id'] = isolate_id

    def get_validation_type(self) -> ResultType:
        return self.get('validation',{}).get('type',None)

    def get_json_results(self) -> JsonReportDict:
        return JsonReportDict(self.get("results"))
