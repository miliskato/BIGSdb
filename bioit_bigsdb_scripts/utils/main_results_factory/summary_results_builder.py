from abc import ABC, abstractmethod
from typing import Optional

from psycopg.types.json import Jsonb
from bioit_mongodb_scripts.model.json_model import JsonReportDict


class SummaryResultsBuilder(ABC):
    """
    Abstract class that sets the contract for MainResultsBuilder
    """

    @abstractmethod
    def accept(self, species: str) -> bool:
        """
        Evaluate if the species should be accepted.
        :param species: name of the species
        :return: True if the species should be accepted by the builder otherwise False
        """
        pass

    @abstractmethod
    def build_json(self, json_report: JsonReportDict) -> Optional[Jsonb]:
        """
        Based on the species, builds the json to be inserted in the analysis_results table
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :return: Jsonb object to be inserted in the analysis_results table
        """
        pass

