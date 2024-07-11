import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from .json_superclass import JsonSuperClass
from .psql import TblAlleleDesignations, TblHistory, TblEavTextHidden, TblEavText


class JsonGeneDetectionResultsInserter(JsonSuperClass):
    """
    Class containing definitions to insert gene detection results from json input
    """
    def __init__(self, isolatename: str, species: str,
                 sample_output_dict: Dict[str, Any], config_data: Dict[str, Any], report_access: str) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param config_data: the bigsdb config data
        :param sample_output_dict: results of sample
        :param report_access: report dir from mongo
        :return: None
        """
        self._report_access = Path(report_access)

        super().__init__(isolatename, species, sample_output_dict, config_data)

        self._genedetectiondict: Union[None, Dict[str, Dict[str, str]]] = self._bigsdb_config_data['species_json'][species]['genedetection_schemes']
        self._eavhtmltable = None
        self._scheme = None
        self._clusterdict = None
        self._ncbi_ab_class_dict = None
        self._schemename_bigsdb = None

    def insert_genedetection_results(self) -> None:
        """
        Inserts genedetection results into bigsdb from json
        :return: None
        """
        if self._genedetectiondict is not None:
            for scheme in self._genedetectiondict:
                if scheme in self._sample_output_dict:
                    self._scheme = scheme
                    self._schemename_bigsdb = self._genedetectiondict[self._scheme]['schemename_bigsdb']
                    # create current clusterdict with names and current cluster
                    self._clusterdict, self._ncbi_ab_class_dict = self._create_clusterdict_current_db_version()
                    # Get hits
                    listofhits: List = self._sample_output_dict[self._scheme]['loci']
                    report_name = self._report_access.name
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

                        html_scheme_name = self._genedetectiondict[self._scheme]['schemename_html']
                        url = f'/galaxyreports/{self._species}/{report_name}/report.html#{html_scheme_name}'
                        if not self._scheme.endswith('vfdb_core') and not self._scheme.endswith('virulencefinder'):
                            self._eavhtmltable = '<style>table.nice { text-align: center; border-spacing:0 }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
                            self._eavhtmltable += f'<table class="data nice"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                            self._eavhtmltable += f'<tr align="left"><td colspan="4"><a href="{url}" target="_blank">Full report</a></td></tr>'
                        else:
                            self._eavhtmltable = f'<a href="{url}" target="_blank">Full report</a>'

                        clusterhitset = set()  # in case loci that were in different clusters at some point get in the same cluster
                        with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl:
                            n = 1
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
                                    self._append_to_htmltable(hit, clusterhit)

                                """
                                Part 2 for the AB schemes
                                """
                                if self._schemename_bigsdb == 'NCBI_AMR' or self._schemename_bigsdb == 'ResFinder':
                                    self._process_ab_schemes(hit, hit_name)

                        # Close Html table
                        self._eavhtmltable += '</table>'
                        with TblEavText(self._species) as isolates_eavt_psql_tbl:
                            isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, self._schemename_bigsdb, self._eavhtmltable))
                else:
                    logging.warning(f"scheme {self._scheme} not present in json file")
            with TblHistory(self._species) as isolates_history_psql_tbl:
                isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Gene detection results inserted'))
            logging.info('Gene detection insertion succesful')

    def _append_to_htmltable(self, hit: Dict[str, str], clusterhit: str) -> None:
        """
        Appends a row to the html table
        :param hit: hit dictionary
        :param clusterhit: current cluster of the hit
        :return: None
        """
        # append Cluster
        gene_cluster = clusterhit.split('Cluster_')[1]
        locus_name: str = hit['Locus']

        self._eavhtmltable += f'<tr><td>{gene_cluster}</td><td>{locus_name}</td></tr>'

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
        if self._schemename_bigsdb == 'NCBI_AMR':
            self._assign_schememember_if_needed(locusname, scheme_name)

    def _process_ab_schemes(self, hit: Dict[str, str], hit_name: str):
        """
        Inserts everything required for antibiotic schemes
        :param hit: hit dictionary
        :param hit_name: hit name: accesision _ locus
        :return:
        """
        # Class scheme for NCBI_AMR only
        if self._schemename_bigsdb == 'NCBI_AMR':
            ncbi_class: str = self._ncbi_ab_class_dict[hit_name]
            self.__process_ab_scheme(ncbi_class, hit, amr_class=True)

        # AB scheme for both ResFinder or NCBI_AMR
        for antibiotic in hit['Antibiotic(s)'].split('/'):
            ab_hit = '_'.join([self._schemename_bigsdb, antibiotic.upper().replace(' ', '_')])
            self.__process_ab_scheme(ab_hit, hit)

    def _create_clusterdict_current_db_version(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Clusters change over time, to be able to link old clusters to new ones, a dictionary is created with the accesion name and allele name
        :return:
        """
        # first create a cluster content list
        ncbi_ab_class_dict: Dict[str, str] = {}
        clusterdict: Dict[str, str] = {}  # e.g. 'accesion1_allele1': 'VFDB_GeneCluster_0'
        with Path(self._genedetectiondict[self._scheme]['metadatafile']).open('r') as handle:
            sequencedictlist: Dict[str, Dict[str, Any]] = json.load(handle)
            for sequencename in sequencedictlist:
                """
                sequencename becomes accession concatenated with allele because in e.g. 
                Resfinder, multiple accessions are not unique.
                sequencedictlist looks like this: 
                {'seq_0': {'accession': 'NG_047553.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 
                           'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 
                           'header_orig': 'NG_047553.1_1567214_ble', 'cluster': 'Cluster_881'}, 
                 'seq_1': {'accession': 'NG_047554.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 
                           'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 
                           'header_orig': 'NG_047554.1_1567214_ble', 'cluster': 'Cluster_881'}, 
                 'seq_2': {'accession': 'NG_056058.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 
                           'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 
                           'header_orig': 'NG_056058.1_BcII', 'cluster': 'Cluster_561'}, 
                 'seq_3': {'accession': 'NG_047221.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 
                           'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 
                           'header_orig': 'NG_047221.1_BcII', 'cluster': 'Cluster_561'}}
                """
                if sequencedictlist[sequencename]['accession'] is None:
                    # in VFDB, there are accessions with name "null", this borke the script,
                    # therefore, now a - is added, and the allele should be enough to find.
                    sequencedictlist[sequencename]['accession'] = "-"
                geneclusternamebigsdb = f"{self._schemename_bigsdb}_Gene{sequencedictlist[sequencename]['cluster']}"
                clusterdict['_'.join([(sequencedictlist[sequencename]['accession']),
                                           (sequencedictlist[sequencename]['allele']).replace("'", "")])] = geneclusternamebigsdb
                if self._schemename_bigsdb == 'NCBI_AMR':
                    ncbi_ab_class_dict['_'.join(
                        [(sequencedictlist[sequencename]['accession']), (sequencedictlist[sequencename]['allele']).replace("'", "")])] = '_'.join(
                        ['NCBI_AMR', sequencedictlist[sequencename]['class'].upper().replace(' ', '_')])

            return clusterdict, ncbi_ab_class_dict
