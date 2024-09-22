from collections import UserDict
from pathlib import Path
from typing import List, Dict, Union, Any
import json

# class Qc:
#     status: str
#
#     def __init__(self, obj: dict = None):
#         if obj is None:
#             return
#         self.status = str(obj.get("status"))
#
# class Loci:
#     Locus: str
#     Allele: str
#     IdentityPercentage: str
#     HSPLocusLength: str
#     Type: str
#
#     def __init__(self, obj: dict = None):
#         if obj is None:
#             return
#
#         self.Locus = str(obj.get("Locus"))
#         self.Allele = str(obj.get("Allele"))
#         self.IdentityPercentage = str(obj.get("% Identity"))
#         self.HSPLocusLength = str(obj.get("HSP/Locus length"))
#         self.Type = str(obj.get("Type"))
#
# class MlstLoci(Loci):
#     def __init__(self, obj: dict = None):
#         super().__init__(obj)
#
#         if obj is None:
#             return
#
# class CgmlstLoci(Loci):
#     def __init__(self, obj: dict = None):
#         super().__init__(obj)
#
#         if obj is None:
#             return
#
# class Mlst:
#     loci: List[MlstLoci]
#
#     def __init__(self, obj: dict = None):
#         if obj is None:
#             return
#
#         self.loci = [MlstLoci(y) for y in obj.get("loci")]
#
# class Cgmlst:
#     loci: List[CgmlstLoci]
#
#     def __init__(self, obj: dict = None):
#         if obj is None:
#             return
#
#         self.loci = [CgmlstLoci(y) for y in obj.get("loci")]
#
# class JsonReport:
#     qc: Dict[str, Qc]
#     mlst: Mlst
#     cgmlst: Cgmlst
#
#     def __init__(self, obj: dict = None):
#         self.qc = {}
#
#         if obj is None:
#             return
#
#         for key in obj.get("qc"):
#             self.qc[key] = Qc(obj.get("qc")[key])
#
#         self.cgmlst = Cgmlst(obj.get("cgmlst"))
#         self.mlst = Mlst(obj.get("mlst"))
#
#     @staticmethod
#     def from_json(path: Union[str, Path]) -> 'JsonReport':
#         with open(path, 'r') as f:
#             json_data = json.load(f)
#         return JsonReport(json_data)

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

