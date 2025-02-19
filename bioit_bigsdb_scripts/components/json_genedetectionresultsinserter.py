import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from .json_superclass import JsonSuperClass
from .psql import TblAlleleDesignations, TblHistory, TblEavTextHidden, TblEavText, TblIsolates
from ..genedetection_intopsql import GeneDetectionIntoPsql
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
        self._scheme = None
        self._clusterdict = None
        self._schemename_bigsdb = None

    def insert_genedetection_results(self) -> None:
        """
        Inserts genedetection results into bigsdb from json
        :return: None
        """
        eavhtmltable = None
        if self._genedetectiondict is not None:
            for scheme in self._genedetectiondict:
                self._scheme = scheme
                if self._scheme in self._json_report_dict:
                    scheme_config = self._genedetectiondict[self._scheme]
                    self._schemename_bigsdb = scheme_config['schemename_bigsdb']
                    # create current clusterdict with names and current cluster

                    context = GeneDetectionIntoPsql.create_gene_detection_context(scheme, scheme_config)
                    self._clusterdict = context.cluster_dict
                    # Get hits
                    listofhits: List = self._json_report_dict[self._scheme]['loci']
                    """
                    this might look something like this currently: 
                    "ncbi_amr": {"loci": 
                    [{"DB_cluster": "Cluster_973", "Locus": "fosA7.4", 
                      "% Identity": "96.07", "HSP/Locus length": "280/423", 
                      "Contig": "NODE_3_length_348793_cov_29.301727", "Position in contig": "289059..289338", 
                      "Antibiotic(s)": "Fosfomycin", "Accession": "NG_067230.1"}]}
                    """
                    if len(listofhits) != 0:
                        # Storing snapshot Clusters in eav_text_hidden to be used in periodical GeneCluster recalculation
                        for index, hit in enumerate(listofhits):
                            for k, v in hit.items():
                                listofhits[index][k] = v.replace("'", "")
                        with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                            isolates_eavth_psql_tbl.insert_hidden_isolate((self._isolatename, self._schemename_bigsdb, json.dumps(listofhits)))

                        html_scheme_name = scheme_config['schemename_html']
                        with TblIsolates(self._species) as isolates_psql_tbl:
                            isolate_id = isolates_psql_tbl.select_id_for_isolate((self._isolatename,))

                        report_url = UrlHelper.report_for_isolate(self._species, str(isolate_id[0][0]), anchor=html_scheme_name)
                        if self._scheme == 'resfinder4':
                            eavhtmltable += '<style>table.nice { text-align: center; border-spacing:0 }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
                            eavhtmltable += f'<table class="data nice"><tr><th>AMR</th><th>Resistance gene</th><th>Resistance gene</th><th>%Identity</th><th>Coverage</th></tr>'
                            for dict in self._json_report_dict[self._scheme]['resfinder4_genes_hits']:
                                eavhtmltable += f'<tr><td>{dict{'Phenotype'}}</td><td>{dict{'Resistance gene'}}</td><td>{dict{'Identity'}}</td><td>{dict{'Coverage'}}</td></tr>'
                            eavhtmltable += f'<tr align="left"><td colspan="4"><a href="{report_url}" target="_blank">Full report</a></td></tr>'
                        if not self._scheme.endswith('vfdb_core') and not self._scheme.endswith('virulencefinder'):
                            eavhtmltable += '<style>table.nice { text-align: center; border-spacing:0 }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
                            eavhtmltable += f'<table class="data nice"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                            eavhtmltable += f'<tr align="left"><td colspan="4"><a href="{report_url}" target="_blank">Full report</a></td></tr>'
                        else:
                            eavhtmltable = f'<a href="{report_url}" target="_blank">Full report</a>'

                        clusterhitset = set()  # in case loci that were in different clusters at some point get in the same cluster
                        with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl:
                            for hit in listofhits:
                                """
                                Part 1 regular gene detection
                                """
                                hit['Locus'] = hit['Locus'].replace("'", "")
                                hit_name = '_'.join([hit['Accession'], hit['Locus']])
                                if self._clusterdict.get(hit_name):
                                    clusterhit: str = self._clusterdict[hit_name]
                                else:
                                    # provided input is probably too old compared to current database, we continue
                                    # to next hit. This issue mainly occurs if no reanalysis is happening and db becomes
                                    # discrepant with results. In this case results are uploaded too long after analysis.
                                    continue
    
                                if clusterhit not in clusterhitset:
                                    isolates_ad_psql_tbl.insert_designation_by_isolatename((clusterhit, self._isolatename, '1'))
    
                                clusterhitset.add(clusterhit)

                                if not self._scheme.endswith('vfdb_core') and not self._scheme.endswith('virulencefinder'):
                                    eavhtmltable += GeneDetectionIntoPsql.create_gene_locus_row(hit, clusterhit)


                                """
                                Part 2 for the AB schemes
                                """
                                if self._schemename_bigsdb == 'NCBI_AMR' or self._schemename_bigsdb == 'ResFinder':
                                    self._process_ab_schemes(hit, hit_name)

                        # Close Html table
                        eavhtmltable += '</table>'
                        with TblEavText(self._species) as isolates_eavt_psql_tbl:
                            isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, self._schemename_bigsdb, eavhtmltable))
                else:
                    logging.warning(f"scheme {self._scheme} not present in json file")
            with TblHistory(self._species) as isolates_history_psql_tbl:
                isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Gene detection results inserted'))
            logging.info('Gene detection insertion succesful')

    def __process_ab_scheme(self, locusname: str, hit: Dict[str, str], amr_class: bool = False) -> None:
        """
        Insert a scheme
        :param locusname: name of the locus
        :param hit: hit dictionary
        :param amr_class: Whether the scheme is a class
        :return:
        """
        genehit = re.sub('[.]| ', '_', hit['Locus'])
        scheme_name = f'{self._schemename_bigsdb}_AB' if not amr_class else f'{self._schemename_bigsdb}_AB_CLASS'
        self.insert_locus_if_needed(locusname, scheme_name)
        self._insert_dummy_sequence_if_needed(locusname, genehit)
        self._insert_ad_if_needed(locusname, genehit)


    def _process_ab_schemes(self, hit: Dict[str, str], hit_name: str):
        """
        Inserts everything required for antibiotic schemes
        :param hit: hit dictionary
        :param hit_name: hit name: accesision _ locus
        :return:
        """
        # AB scheme for both ResFinder4
        for antibiotic in hit['Antibiotic(s)'].split('/'):
            ab_hit = '_'.join([self._schemename_bigsdb, antibiotic.upper().replace(' ', '_')])
            self.__process_ab_scheme(ab_hit, hit)
