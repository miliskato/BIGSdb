from psycopg.types.json import Jsonb

from factories.main_results_factory.data_typing.serotyping_results import SerotypingData
from factories.main_results_factory.utils.json_maker_summary_results import JsonMakerSummaryResults
from factories.main_results_factory.builders.summary_results_builder import SummaryResultsBuilder
from bioit_mongodb_scripts.model.json_model import JsonReportDict
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider


class GenericSummaryResultsBuilder(SummaryResultsBuilder):

    def accept(self, species: str) -> bool:
        """
        Accept or reject the species
        :param species: name of the species
        :return: True if accepted, False otherwise
        """
        return MongoConfigProvider.is_viral(species) is False

    def build_json(self, json_report: JsonReportDict, species: str) -> Jsonb:
        """
        Builds the json to be inserted in the analysis_results table
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :param species: name of the species currently processed
        :return: Jsonb object to be inserted in the analysis_results table
        """

        st_data = self.extract_sequence_typing_data(json_report)
        sg_data = SerotypingData(json_report.get('serogroup'))

        json_maker = JsonMakerSummaryResults(species, st_data, sg_data)

        return json_maker.create_binary_json()
