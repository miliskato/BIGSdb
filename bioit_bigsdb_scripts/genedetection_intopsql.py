import argparse
import json
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.json_superclass import JsonSuperClass
from bioit_bigsdb_scripts.components.psql import TblLocusDescriptions, TblLoci, TblSequences, TblAlleleDesignations, TblEavText, TblEavTextHidden, TblHistory
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying


def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=specieslist, default=specieslist, nargs='+')  # this does allow for the same species multiple times but doesnt really matter, theyre uniquely filtered using set()
    return argument_parser.parse_args()


class GeneDetectionIntoPsql:
    """
    Initialises the class and runs the main function.
    See also argparse function for variables and their requiredness.
    :param species: commonly used bioit species name: either genus or specific like stec
    :param bigsdb_config_data: the config data containing all configuration settings for bigsdb
    :return: None
    """
    def __init__(self, bigsdb_config_data: Dict[str, Any], species: str) -> None:
        self._bigsdb_config_data = bigsdb_config_data
        self._species = species
        self._schemedict: Dict[str, Any] = self._bigsdb_config_data['species'][self._species]['genedetection_schemes']
        self._gene_detection_insertion_and_recalculation()
        self._eavhtmltable = None

    def _gene_detection_insertion_and_recalculation(self) -> None:
        """
        Inserts gene detection loci and alleles and recalculates existing loci/alleles
        Recalculation pertains the Clusters which are recalculated weekly on often 80% identity
        :return: None
        """
        if self._schemedict is not None:
            for scheme in self._schemedict:
                self._scheme: str = scheme

                self.__create_necessary_dictionaries()

                self.__insert_loci_and_alleles()

                self.__update_locus_descriptions()

                self.__recalculate_allele_designations()

    def __create_necessary_dictionaries(self) -> None:
        """
        Creates the necessary dictionaries of the current database version
        :return: None
        """
        self._descriptiondict: Dict[str, List[str]] = {}  # e.g. 'VFDB_GeneCluster_0' : ['gene1', 'gene2']
        self._clusterdict: Dict[str, str] = {}  # e.g. 'accesion1_allele1': 'VFDB_GeneCluster_0'
        with Path(self._schemedict[self._scheme]['metadatafile']).open('r') as handle:
            sequencedictlist: Dict[str, Dict[str, Any]] = json.load(handle)
            for sequencename in sequencedictlist:
                """
                sequencename becomes accession concatenated with allele because in e.g. 
                Resfinder, multiple accessions are not unique.
                sequencefile looks like this: 
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
                    sequencedictlist[sequencename]['accession'] = "-"
                geneclusternamebigsdb = f"{self._schemedict[self._scheme]['schemename_bigsdb']}_Gene{sequencedictlist[sequencename]['cluster']}"
                self._clusterdict['_'.join([(sequencedictlist[sequencename]['accession']),
                                            (sequencedictlist[sequencename]['allele']).replace("'", "")])] = geneclusternamebigsdb
                if not self._descriptiondict.get(geneclusternamebigsdb):
                    self._descriptiondict[geneclusternamebigsdb] = []
                if self._schemedict[self._scheme]['schemename_bigsdb'] != 'VFDB_core':
                    self._descriptiondict[geneclusternamebigsdb].append(
                        (sequencedictlist[sequencename]['allele']).replace("'", ""))
                else:
                    self._descriptiondict[geneclusternamebigsdb].append(
                        (sequencedictlist[sequencename]['gene']).replace("'", ""))
        self._clusterlist = list(self._descriptiondict.keys())

    def __insert_loci_and_alleles(self) -> None:
        """
        Inserts all the loci (clusters), scheme members and alleles (dummy boolean) in seqdef and isolate dbs if they are not present
        :return: None
        """
        json_superclass_instance = JsonSuperClass('dummyname', self._species, {'dummydictkey': 'dummydictvalue'}, config_data=self._bigsdb_config_data)
        with TblSequences(self._species) as seqdef_sequences_psql_tbl, TblLoci(self._species, 'seqdef') as seqdef_loci_psql_tbl:
            for cluster in self._clusterlist:
                present: List[Tuple[int]] = seqdef_loci_psql_tbl.count_locus((cluster,))
                if present[0][0] == 0:
                    json_superclass_instance.insert_locus_if_needed(
                        cluster, self._schemedict[self._scheme]['schemename_bigsdb'])
                    seqdef_sequences_psql_tbl.insert_sequence((cluster, '1', 'dummy1'))
                    seqdef_sequences_psql_tbl.insert_sequence((cluster, '0', 'null allele'))
                else:
                    continue

    def __update_locus_descriptions(self) -> None:
        """
        Updates the locus descriptions to the new database version
        :return: None
        """
        with TblLocusDescriptions(self._species) as seqdef_locdescr_psql_tbl:
            seqdef_locdescr_psql_tbl.delete_locus_description((f"{self._schemedict[self._scheme]['schemename_bigsdb']}_GeneCluster%",))
            for cluster, description in self._descriptiondict.items():
                # convert list to more meaningfull and aesthatically pleasing string
                descriptionstring = ' '.join(['Contains genes:', ', '.join([x for x in description])])
                seqdef_locdescr_psql_tbl.insert_locus_description((cluster, descriptionstring.replace('Contains genes:', ''), descriptionstring))

    def __recalculate_allele_designations(self) -> None:
        """
        Removes, recaculates and reinserts allele designations
        :return: None
        """
        with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl, \
                TblEavText(self._species) as isolates_eavt_psql_tbl, \
                TblHistory(self._species) as isolates_history_psql_tbl:
            isolates_ad_psql_tbl.delete_designations((f"{self._schemedict[self._scheme]['schemename_bigsdb']}_GeneCluster%",))
            with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                listofsamplesandhits = isolates_eavth_psql_tbl.select_hidden((self._schemedict[self._scheme]['schemename_bigsdb'],))
            if len(listofsamplesandhits) > 0:
                for sampleandhits in listofsamplesandhits:
                    isolate_id: str = sampleandhits[0]
                    isolate_name: str = sampleandhits[2]
                    report_dir: str = self.___get_report_name_from_mongo(isolate_name)
                    report_name = Path(report_dir).name
                    html_scheme_name = self._schemedict[self._scheme]['schemename_html']
                    url = f'/galaxyreports/{self._species}/{report_name}/report.html#{html_scheme_name}'
                    if not self._scheme.endswith('vfdbcore'):
                        self._eavhtmltable = '<style>table.nice { text-align: center; border-spacing:0 }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
                        self._eavhtmltable += f'<table class="data nice"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                        self._eavhtmltable += f'<tr align="left"><td colspan="4"><a href="{url}" target="_blank">Full report</a></td></tr>'
                    else:
                        self._eavhtmltable = f'<a href="{url}" target="_blank">Full report</a>'

                    clusterhitset = set()  # in case loci that were in different clusters at some point get in the same cluster
                    hits = json.loads(sampleandhits[1])
                    if len(hits) != 0:
                        for y in range(len(hits)):
                            if isinstance(hits[y], list):
                                # allele is always position 1 and accession is always last position (-1)
                                hit = '_'.join([hits[y][-1], hits[y][1]])
                                clusterhit: str = self._clusterdict[hit]
                                self.___append_to_htmltable(hit, clusterhit)

                            elif isinstance(hits[y], dict):
                                hit = '_'.join([hits[y]['Accession'], hits[y]['Locus']])
                                clusterhit = self._clusterdict[hit]
                                if not self._scheme.endswith('vfdbcore'):
                                    self.___append_to_htmltable(hits[y], clusterhit)

                            if clusterhit not in clusterhitset:
                                isolates_ad_psql_tbl.insert_designation_by_isolateid((clusterhit, isolate_id, '1'))
                                clusterhitset.add(clusterhit)

                    self._eavhtmltable += f'</table>'
                    isolates_eavt_psql_tbl.delete_eav(
                        (isolate_id, self._schemedict[self._scheme]['schemename_bigsdb']))
                    isolates_eavt_psql_tbl.insert_eav_id(
                        (isolate_id, self._schemedict[self._scheme]['schemename_bigsdb'], self._eavhtmltable))
                    isolates_history_psql_tbl.insert_history_id(
                        (isolate_id, 'Gene detection results reevaluated after database update'))

    def ___get_report_name_from_mongo(self, samplename: str) -> Union[str, Path]:
        """
        Get the name of the html report for the given isolate
        :param samplename: name of the isolate
        :return: report name for the isolate
        """
        mongoinit = MongoInitialisation(species=self._species, mongo_config_data=get_mongodb_config_data())
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
        isolate_report_path = Mongoquerying.query_docs_by_ids(opened_collection=isolates_collection, ids=[samplename])
        return isolate_report_path[0]['report_directory']

    def ___append_to_htmltable(self, hit: Dict[str, str], clusterhit: str) -> None:
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


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    try:
        for species in set(args.species):
            GeneDetectionIntoPsql(bigsdb_config_data, species)
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")
