import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import psycopg2.extensions

from .databaseconnection import DatabaseConnection
from .json_superclass import JsonSuperClass


class JsonGeneDetectionResultsInserter(JsonSuperClass):
    """
    Class containing definitions to insert gene detection results from json input
    """

    def __init__(self, isolatename: str, species: str, cur_isolates: DatabaseConnection, cur_seqdef: DatabaseConnection,
                 sample_output_dict: Dict[str, Any], config_data: Dict[str, Any]) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param cur_isolates: isolate database connection object
        :param cur_seqdef: sequence definition database connection object
        :param config_data: the bigsdb config data
        :param sample_output_dict: results of sample
        :return: None
        """
        JsonSuperClass.__init__(self, isolatename, species, cur_isolates, cur_seqdef, sample_output_dict, config_data)
        self.genedetectiondict: Union[None, Dict[str, Dict[str, str]]] = config_data['species_json'][species]['genedetection_schemes']

    def insert_genedetection_results(self) -> None:
        """
        Inserts genedetection results into bigsdb from json
        :return: None
        """
        if self.genedetectiondict is not None:
            for scheme in self.genedetectiondict:
                if scheme in self.sample_output_dict:
                    # create current clusterdict with names and current cluster
                    clusterdict, ncbi_ab_class_dict = self._create_clusterdict_current_db_version(scheme)
                    # Get hits
                    listofhits: List = self.sample_output_dict[scheme]['loci']
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
                        self._insert_metadata_hidden(self.genedetectiondict[scheme]['schemename_bigsdb'], json.dumps(listofhits))
                        eavhtmltable: str = '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                        clusterhitset: set = set()  # in case loci that were in different clusters at some point get in the same cluster
                        for hit in listofhits:
                            """
                            Part 1 regular gene detection
                            """
                            hit['Locus']: str = hit['Locus'].replace("'", "")
                            hit_name: str = '_'.join([hit['Accession'], hit['Locus']])
                            if clusterdict.get(hit_name):
                                clusterhit: str = clusterdict[hit_name]
                            else:
                                # provided input is probably too old compared to current database, we continue
                                # to next hit. This issue mainly occurs if no reanalysis is happening and db becomes
                                # discrepant with results. In this case results are uploaded too long after analysis.
                                continue

                            if clusterhit not in clusterhitset:
                                self._insert_allele_designation(clusterhit, '1')

                            clusterhitset.add(clusterhit)
                            # append Cluster
                            eavhtmltable: str = eavhtmltable + ''.join(
                                ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                            # append Locus
                            locusname: str = hit['Gene'] if scheme.endswith('vfdbcore') else hit['Locus']
                            eavhtmltable: str = eavhtmltable + ''.join(
                                [f'<td><a href="/galaxyreports/{self.species}/', self.isolatename, '/report.html#',
                                 self.genedetectiondict[scheme]['schemename_html'], '" target="_blank">',
                                 locusname, '</a></td></tr>'])

                            """
                            Part 2 for the AB schemes
                            """""
                            if self.genedetectiondict[scheme]['schemename_bigsdb'] == 'NCBI_AMR':
                                ncbi_class: str = ncbi_ab_class_dict[hit_name]
                                genehit: str = re.sub('[.]| ', '_', hit['Locus'])
                                self._insert_locus_if_needed(ncbi_class, 'NCBI_AMR_AB_CLASS')
                                self._assign_schememember_if_needed(ncbi_class, 'NCBI_AMR_AB_CLASS')
                                self._insert_dummy_sequence_if_needed(ncbi_class, genehit)
                                self._insert_ad_if_needed(ncbi_class, genehit)

                                for antibiotic in hit['Antibiotic(s)'].split('/'):
                                    ab_hit: str = '_'.join(['NCBI_AMR', antibiotic.upper().replace(' ', '_')])
                                    self._insert_locus_if_needed(ab_hit, 'NCBI_AMR_AB')
                                    self._assign_schememember_if_needed(ab_hit, 'NCBI_AMR_AB')
                                    self._insert_dummy_sequence_if_needed(ab_hit, genehit)
                                    self._insert_ad_if_needed(ab_hit, genehit)

                            elif self.genedetectiondict[scheme]['schemename_bigsdb'] == 'ResFinder':
                                genehit: str = re.sub('[.]| ', '_', hit['Locus'])
                                for antibiotic in hit['Antibiotic(s)'].split('/'):
                                    ab_hit = '_'.join(['ResFinder', antibiotic.upper().replace(' ', '_')])
                                    self._insert_locus_if_needed(ab_hit, 'ResFinder_AB')
                                    self._insert_dummy_sequence_if_needed(ab_hit, genehit)
                                    self._insert_ad_if_needed(ab_hit, genehit)

                        # Close Html table
                        eavhtmltable: str = eavhtmltable + '</table>'
                        self._insert_metadata(self.genedetectiondict[scheme]['schemename_bigsdb'], eavhtmltable)
                else:
                    logging.warning(f"scheme {scheme} not present in json file")
            self._insert_history('Gene detection results inserted')
            logging.info('Gene detection insertion succesful')

    def _create_clusterdict_current_db_version(self, scheme: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Clusters change over time, to be able to link old clusters to new ones, a dictionary is created with the accesion name and allele name
        :param scheme: gene detection scheme
        :return:
        """
        # first create a cluster content list
        ncbi_ab_class_dict: Dict[str, str] = {}
        clusterdict: Dict[str, str] = {}  # e.g. 'accesion1_allele1': 'VFDB_GeneCluster_0'
        with Path(self.genedetectiondict[scheme]['metadatafile']).open('r') as handle:
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
                geneclusternamebigsdb: str = f"{self.genedetectiondict[scheme]['schemename_bigsdb']}_Gene{sequencedictlist[sequencename]['cluster']}"
                clusterdict['_'.join([(sequencedictlist[sequencename]['accession']),
                                           (sequencedictlist[sequencename]['allele']).replace("'", "")])] = geneclusternamebigsdb
                if self.genedetectiondict[scheme]['schemename_bigsdb'] == 'NCBI_AMR':
                    ncbi_ab_class_dict['_'.join(
                        [(sequencedictlist[sequencename]['accession']), (sequencedictlist[sequencename]['allele']).replace("'", "")])] = '_'.join(
                        ['NCBI_AMR', sequencedictlist[sequencename]['class'].upper().replace(' ', '_')])

            return clusterdict, ncbi_ab_class_dict
