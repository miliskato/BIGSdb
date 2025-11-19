from typing import Optional

from psycopg.types.json import Jsonb

from factories.main_results_factory.utils.json_maker_summary_results import JsonMakerSummaryResults
from factories.main_results_factory.builders.summary_results_builder import SummaryResultsBuilder
from factories.main_results_factory.data_typing.sequence_typing_results import NeisseriaSequenceTypingData
from factories.main_results_factory.data_typing.serotyping_results import NeisseriaSerotypingData, SerotypingData
from bioit_mongodb_scripts.model.json_model import JsonReportDict


class NeisseriaSummaryResultsBuilder(SummaryResultsBuilder):

    SPECIES_NAME = 'neisseria'

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

        st_data = self.extract_sequence_typing_data(json_report)
        pora_vr1 = json_report['pora']['loci'][0].get('Allele')
        pora_vr2 = json_report['pora']['loci'][1].get('Allele')
        porb = json_report['porb']['loci'][0].get('Allele')
        neisseria_st_add_data = NeisseriaSequenceTypingData(pora_vr1, pora_vr2, porb)

        sg_results = json_report.get('serogroup')
        sg_data = SerotypingData(sg_results['serogroup_legacy'])
        neisseria_sg_add_data = NeisseriaSerotypingData(sg_results['serogroup_capsule'])

        json_maker = JsonMakerSummaryResults(st_data, sg_data)

        return json_maker.create_binary_json(neisseria_st_add_data, neisseria_sg_add_data)
