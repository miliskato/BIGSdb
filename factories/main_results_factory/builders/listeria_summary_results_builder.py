from typing import Optional

from psycopg.types.json import Jsonb

from factories.main_results_factory.utils.json_maker_summary_results import JsonMakerSummaryResults
from factories.main_results_factory.builders.summary_results_builder import SummaryResultsBuilder
from factories.main_results_factory.data_typing.sequence_typing_results import ListeriaSequenceTypingData
from factories.main_results_factory.data_typing.serotyping_results import SerotypingData
from bioit_mongodb_scripts.model.json_model import JsonReportDict


class ListeriaSummaryResultsBuilder(SummaryResultsBuilder):

    SPECIES_NAME = 'listeria'

    def accept(self, species: str) -> bool:
        """
        Accept or reject the species
        :param species: name of the species
        :return: True if accepted, False otherwise
        """
        return species == self.SPECIES_NAME

    def build_json(self, json_report: JsonReportDict, species: str) -> Optional[Jsonb]:
        """
        Builds the json to be inserted in the analysis_results table
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :param species: name of the species currently processed
        :return: Jsonb object to be inserted in the analysis_results table
        """

        st_data = self.extract_sequence_typing_data(json_report)
        mlst_cc = json_report['mlst'].get('mlst-CC')
        mlst_lineage = json_report['mlst'].get('mlst-Lineage')

        listeria_st_add_data = ListeriaSequenceTypingData(mlst_cc, mlst_lineage)

        sg_results = json_report['pcr_serogroup'].get('pcr_serogroup-serogroup')
        sg_data = SerotypingData(sg_results)

        json_maker = JsonMakerSummaryResults(species, st_data, sg_data)

        return json_maker.create_binary_json(additional_sequencing_data=listeria_st_add_data)
