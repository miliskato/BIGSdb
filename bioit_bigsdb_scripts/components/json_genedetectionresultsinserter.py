import logging
from pathlib import Path
from typing import Any, Dict, Union

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from .json_superclass import JsonSuperClass
from .psql import TblHistory, TblIsolates
from ..inserters.context.gene_detection_context_builder_factory import GeneDetectionContextBuilderFactory


class JsonGeneDetectionResultsInserter(JsonSuperClass):
    """
    Class containing definitions to insert gene detection results from json input
    """

    def __init__(self, isolatename: str, species: str,
                 json_report_dict: JsonReportDict, config_data: Dict[str, Any], report_access: str) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param config_data: the bigsdb config data
        :param json_report_dict: results of sample
        :param report_access: report dir from mongo
        :return: None
        """
        self._report_access = Path(report_access) # TODO check if still used

        super().__init__(isolatename, species, json_report_dict, config_data)

        self._genedetectiondict: Union[None, Dict[str, Dict[str, str]]] = \
            self._bigsdb_config_data['species_json'][species]['genedetection_schemes']

    def insert_genedetection_results(self) -> None:
        """
        Inserts genedetection results into bigsdb from json
        :return: None
        """
        if self._genedetectiondict is None:
            return

        with TblIsolates(self._species) as isolates_psql_tbl:
            isolate_id = isolates_psql_tbl.select_id_for_isolate((self._isolatename,))

        context_builder_factory = GeneDetectionContextBuilderFactory()

        for scheme in self._genedetectiondict:
            if scheme not in self._json_report_dict:
                logging.warning(f"scheme {scheme} not present in json file")
                continue

            scheme_config = self._genedetectiondict[scheme]

            context_builder_factory.build(scheme, scheme_config)

            if scheme == 'resfinder4':
                list_of_hits = self._json_report_dict[scheme]['resfinder4_genes_hits']
            elif scheme == 'amrfinder':
                list_of_hits = self._json_report_dict[scheme]['amr_genes_hits']
            elif scheme == 'lrefinder':
                if self._json_report_dict[scheme]['lrefinder_genes'][0].get('Gene') == 'Unknown':
                    continue
                list_of_hits = self._json_report_dict['lrefinder']['lrefinder_genes']
            elif scheme.endswith('vfdb_core') or scheme.endswith('virulencefinder'):
                # TODO adapt -> what to do with the reportlink?
                continue
            else:
                list_of_hits = self._json_report_dict[scheme]['loci']

            if len(list_of_hits) != 0:
                self._insert_analysis_results(str(isolate_id[0][0]), scheme, scheme_config)

        with TblHistory(self._species) as isolates_history_psql_tbl:
            isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Gene detection results inserted'))
        logging.info(f'Gene detection insertion for {self._isolatename} is done')
