from abc import ABC, abstractmethod

from psycopg.types.json import Jsonb


class MainResultsBuilder(ABC):
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
    def build(self, species: str) -> Jsonb:
        """
        Based on the species, builds the json to be inserted in the analysis_results table
        :param species: name of the species
        :return: Jsonb object to be inserted in the analysis_results table
        """
        pass