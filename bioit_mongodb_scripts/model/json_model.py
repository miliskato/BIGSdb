from collections import UserDict
from pathlib import Path
from typing import List, Dict, Union, Any
import json

class BridgeDict(UserDict):
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
    @staticmethod
    def from_json(path: Union[str, Path]) -> 'JsonReportDict':
        with open(path, 'r') as f:
            return JsonReportDict(json.load(f))

class MongoRecordDict(BridgeDict):
    def get_id(self) -> str:
        return self.get('_id')

    def get_json_results(self) -> JsonReportDict:
        return JsonReportDict.from_json(self.get("results"))

