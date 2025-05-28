import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Union

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from .json_superclass import JsonSuperClass
from .psql import TblAlleleDesignations, TblEavText, TblEavTextHidden, TblHistory, TblIsolates
from ..inserters.context.gene_detection_context_builder_factory import GeneDetectionContextBuilderFactory
from ..utils.html_tbl_templates import HtmlAmrTableBuilder, HtmlLocusTableBuilder
from ..utils.url_helper import UrlHelper


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
        self._report_access = Path(report_access)

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

        context_builder_factory = GeneDetectionContextBuilderFactory()

        for scheme in self._genedetectiondict:
            if scheme not in self._json_report_dict:
                logging.warning(f"scheme {scheme} not present in json file")
                continue

            scheme_config = self._genedetectiondict[scheme]
            schemename_bigsdb = scheme_config['schemename_bigsdb']
            # create current clusterdict with names and current cluster

            context = context_builder_factory.build(scheme, scheme_config)
            clusterdict = context.cluster_dict
            # Get hits
            if scheme == 'resfinder4':
                listofhits: List = self._json_report_dict[scheme]['resfinder4_genes_hits']
            elif scheme == 'amrfinder':
                listofhits: List = self._json_report_dict[scheme]['amr_genes_hits']
            else:
                listofhits: List = self._json_report_dict[scheme]['loci']

            if len(listofhits) != 0:
                # Storing snapshot Clusters in eav_text_hidden to be used in periodical GeneCluster recalculation
                for index, hit in enumerate(listofhits):
                    for k, v in hit.items():
                        v = v.replace("'", "") if scheme not in ['resfinder4', 'amrfinder'] else v
                        listofhits[index][k] = v
                with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                    isolates_eavth_psql_tbl.insert_hidden_isolate((self._isolatename, schemename_bigsdb, json.dumps(listofhits)))

                html_scheme_name = scheme_config['schemename_html']
                with TblIsolates(self._species) as isolates_psql_tbl:
                    isolate_id = isolates_psql_tbl.select_id_for_isolate((self._isolatename,))

                report_url = UrlHelper.report_for_isolate(self._species, str(isolate_id[0][0]), anchor=html_scheme_name)
                html = f'<a href="{report_url}" target="_blank">Full report</a>'

                if scheme == 'resfinder4':
                    resfinder4_table_builder = HtmlAmrTableBuilder(report_url)
                    for hit in self._json_report_dict[scheme]['resfinder4_genes_hits']:
                        identity = f'{round(float(hit["Identity"]), 2)}'
                        coverage = f'{round(float(hit["Coverage"]), 2)}'
                        resfinder4_table_builder.add_hit(hit['Phenotype'], hit['Resistance gene'], identity, coverage)
                    html = resfinder4_table_builder.build()
                elif scheme == 'amrfinder':
                    amrfinder_table_builder = HtmlAmrTableBuilder(report_url)
                    for hit in self._json_report_dict[scheme]['amr_genes_hits']:
                        identity = f'{round(float(hit["% Identity to reference sequence"]), 2)}'
                        coverage = f'{round(float(hit["% Coverage of reference sequence"]), 2)}'
                        amrfinder_table_builder.add_hit(hit['Subclass'], hit['Gene symbol'], identity, coverage)
                    html = amrfinder_table_builder.build()
                elif not scheme.endswith('vfdb_core') and not scheme.endswith('virulencefinder'):
                    locus_table_builder = HtmlLocusTableBuilder(report_url)
                    clusterhitset = set()  # in case loci that were in different clusters at some point get in the same cluster
                    with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl:
                        for hit in listofhits:
                            """
                            Part 1 regular gene detection
                            """
                            hit['Locus'] = hit['Locus'].replace("'", "")
                            hit_name = '_'.join([hit['Accession'], hit['Locus']])
                            if clusterdict.get(hit_name):
                                clusterhit: str = clusterdict[hit_name]
                            else:
                                # provided input is probably too old compared to current database (no reanalysis case)
                                continue

                            if clusterhit not in clusterhitset:
                                isolates_ad_psql_tbl.insert_designation_by_isolatename(
                                    (clusterhit, self._isolatename, '1'))

                            clusterhitset.add(clusterhit)
                            locus_table_builder.add_locus(hit_name, clusterhit)

                    html = locus_table_builder.build()

                with TblEavText(self._species) as isolates_eavt_psql_tbl:
                    isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, schemename_bigsdb, html))
        with TblHistory(self._species) as isolates_history_psql_tbl:
            isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Gene detection results inserted'))
        logging.info(f'Gene detection insertion for {self._isolatename} is done')
