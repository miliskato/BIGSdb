from typing import Optional

from psycopg.types.json import Jsonb

from bioit_bigsdb_scripts.utils.main_results_factory.json_maker_summary_results import JsonMakerSummaryResults
from bioit_bigsdb_scripts.utils.main_results_factory.summary_results_builder import SummaryResultsBuilder
from bioit_bigsdb_scripts.utils.sequence_typing_results import SequenceTypingData
from bioit_mongodb_scripts.model.json_model import JsonReportDict


class GenericSummaryResultsBuilder(SummaryResultsBuilder):


    def accept(self, species: str) -> bool:
        """
        Accept or reject the species
        :param species: name of the species
        :return: True if accepted, False otherwise
        """
        if not is_viral(species):
            return True

    def build_json(self, json_report: JsonReportDict) -> Jsonb:
        """
        Builds the json to be inserted in the analysis_results table
        :param json_report: JsonReportDict object containing the results from the WGS analysis
        :return: Jsonb object to be inserted in the analysis_results table
        """

        results = json_report
        cgst = results.get('cgST')
        st = results['mlst'].get('mlst-ST')
        rst = results['rmlst'].get('rmlst-rST')
        st_data = SequenceTypingData(cgst, st, rst)

        sg_results = results.get('serogroup')

        json_maker = JsonMakerSummaryResults(st_data, sg_data)

        return json_maker.create_binary_json()
