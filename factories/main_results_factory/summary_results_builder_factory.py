from typing import Optional

from psycopg.types.json import Jsonb

from factories.main_results_factory.builders.generic_summary_results_builder import GenericSummaryResultsBuilder
from factories.main_results_factory.builders.listeria_summary_results_builder import ListeriaSummaryResultsBuilder
from factories.main_results_factory.builders.neisseria_summary_results_builder import NeisseriaSummaryResultsBuilder
from factories.main_results_factory.builders.summary_results_builder import SummaryResultsBuilder
from bioit_mongodb_scripts.model.json_model import JsonReportDict
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider


class SummaryResultsBuilderFactory:
    """
    Factory class to create the json results summary based on the species.
    It can handle the builders specified in the constructor.""
    """

    def __init__(self):
        """Initiates the list of species specific builders. The more generic builder must be kept as the last one in the list"""
        self.summary_results_builders: list[SummaryResultsBuilder] = [
            NeisseriaSummaryResultsBuilder(),
            ListeriaSummaryResultsBuilder(),
            GenericSummaryResultsBuilder()
        ]

    def build_json_report(self, species: str, json_report: JsonReportDict) -> Optional[Jsonb]:
        """
        This method calls the right summary results builder among those specified in the constructor.
        :param species: The species for which a json results summary is needed
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :return: A Jsonb object to be inserted in the analysis_results table
        """
        for results_builder in self.summary_results_builders:
            if results_builder.accept(species):
                return results_builder.build_json(json_report)
            elif MongoConfigProvider.is_viral(species):
                return None
        raise Exception("Results builder not found for species {}".format(species))
