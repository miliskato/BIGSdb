from typing import Optional

from psycopg.types.json import Jsonb

from factories.main_results_factory.utils.json_maker_summary_results import JsonMakerSummaryResults
from factories.main_results_factory.builders.summary_results_builder import SummaryResultsBuilder
from factories.main_results_factory.data_typing.sequence_typing_results import ListeriaSequenceTypingData, SequenceTypingData
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

    def build_json(self, json_report: JsonReportDict) -> Optional[Jsonb]:
        """
        Builds the json to be inserted in the analysis_results table
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :return: Jsonb object to be inserted in the analysis_results table
        """

        results = json_report
        cgst = results.get('cgST')
        mlst_results = results.get('mlst')
        st = mlst_results.get('mlst-ST')
        rst = results['rmlst'].get('rmlst-rST')
        st_data = SequenceTypingData(cgst, st, rst)

        listeria_st_data = ListeriaSequenceTypingData(mlst_results.get('mlst-CC'), mlst_results.get('lineage'))

        sg_results = results.get('pcr_serogroup')
        sg_data = SerotypingData(sg_results.get('pcr_serogroup-serogroup'))

        json_maker = JsonMakerSummaryResults(st_data, sg_data)

        return json_maker.create_binary_json(additional_sequencing_data=listeria_st_data)
