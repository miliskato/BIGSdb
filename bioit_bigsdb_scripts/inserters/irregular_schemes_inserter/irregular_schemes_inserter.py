from abc import ABCMeta, abstractmethod
from typing import Any, Dict

from bioit_mongodb_scripts.model.json_model import JsonReportDict


class IrregularSchemesInserter(metaclass=ABCMeta):
    """
    Abstract class that sets the contract for GeneDetectionContext
    """
    @abstractmethod
    def accept(self, species: str) -> bool:
        """
        Evaluate if the scheme should be accepted.
        :param species: name of the species
        :return: True if the scheme should be accepted by the builder
        """
        pass

    @abstractmethod
    def insert_scheme(self, species: str, scheme: str, scheme_config: Dict[str, Any], json_report: JsonReportDict, isolate_name: str) -> None:
        """
        process the insertion of results for a given isolate and a specific irregular scheme.
        """
        pass