from abc import ABC, abstractmethod
from typing import Optional

from psycopg.types.json import Jsonb
from bioit_mongodb_scripts.model.json_model import JsonReportDict
from factories.main_results_factory.data_typing.sequence_typing_results import SequenceTypingData


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
    def build_json(self, json_report: JsonReportDict, species: str) -> Optional[Jsonb]:
        """
        Based on the species, builds the json to be inserted in the analysis_results table
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :param species: name of the species currently processed
        :return: Jsonb object to be inserted in the analysis_results table
        """
        pass

    @staticmethod
    def extract_sequence_typing_data(json_report: JsonReportDict) -> SequenceTypingData:
        """
        Helper to extract common sequence typing fields and return a SequenceTypingData.
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :return: SequenceTypingData object
        """
        results = json_report
        cgst = results.get('cgST')
        st = results['mlst'].get('mlst-ST')
        rst = results['rmlst'].get('rmlst-rST')
        return SequenceTypingData(cgst, st, rst)
