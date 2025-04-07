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
from bioit_bigsdb_scripts.utils.url_helper import UrlHelper
from bioit_mongodb_scripts.model.json_model import JsonReportDict
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
    argument_parser.add_argument('--do_not_recalculate', required=False, action='store_true', default=False)  # Since 2024/03/29 this script accesses Mongo directly to recalculate, in some instances mongo is not instantiated yet when this script is called (moving from local to Azure), requiring the ability to disable the recalculation
    return argument_parser.parse_args()


class GeneDetectionIntoPsql:
    """
    Class containing function to insert gene detection loci and alleles and update them
    """
    def __init__(self, species_list: List[str], do_not_recalculate: bool, dont_send_email: bool = False) -> None:
        """
        Initialises this class and executes the main function: _gene_detection_insertion_and_recalculation
        :param species_list: list of commonly used bioit species name: either genus or specific like stec.
        :param do_not_recalculate: Whether the recalculation step should be skipped or not.
        :param dont_send_email: do not send emails, only log
        :return: None
        """
        self._species_list = species_list
        self._do_not_recalculate = do_not_recalculate
        self._dont_send_email = dont_send_email

        self._bigsdb_config_data = get_bigsdb_config_data()

        try:
            for species in set(self._species_list):
                self._schemedict: Dict[str, Any] = self._bigsdb_config_data['species'][species].get('genedetection_schemes')
                self._gene_detection_insertion_and_recalculation(species)
                self._eavhtmltable = None
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

    def _gene_detection_insertion_and_recalculation(self, species: str) -> None:
        """
        Inserts gene detection loci and alleles and recalculates existing loci/alleles
        Recalculation pertains the Clusters which are recalculated weekly on often 80% identity
        :param species: commonly used bioit species name: either genus or specific like stec.
        :return: None
        """
        if self._schemedict is not None:
            for scheme in self._schemedict:
                self._scheme: str = scheme

                self.__create_necessary_dictionaries()

                self.__insert_loci_and_alleles(species)

                self.__update_locus_descriptions(species)

                if not self._do_not_recalculate:
                    self.__recalculate_allele_designations(species)

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

    def __insert_loci_and_alleles(self, species: str) -> None:
        """
        Inserts all the loci (clusters), scheme members and alleles (dummy boolean) in seqdef and isolate dbs if they are not
        :param species: commonly used bioit species name: either genus or specific like stec.
        :return: None
        """
        json_superclass_instance = JsonSuperClass('dummyname', species, JsonReportDict({'dummydictkey': 'dummydictvalue'}), config_data=self._bigsdb_config_data)
        with TblSequences(species) as seqdef_sequences_psql_tbl, TblLoci(species, 'seqdef') as seqdef_loci_psql_tbl:
            for cluster in self._clusterlist:
                present: List[Tuple[int]] = seqdef_loci_psql_tbl.count_locus((cluster,))
                if present[0][0] == 0:
                    json_superclass_instance.insert_locus_if_needed(
                        cluster, self._schemedict[self._scheme]['schemename_bigsdb'])
                    seqdef_sequences_psql_tbl.insert_sequence((cluster, '1', 'dummy1'))
                    seqdef_sequences_psql_tbl.insert_sequence((cluster, '0', 'null allele'))
                else:
                    continue

    def __update_locus_descriptions(self, species: str) -> None:
        """
        Updates the locus descriptions to the new database version
        :param species: commonly used bioit species name: either genus or specific like stec.
        :return: None
        """
        with TblLocusDescriptions(species) as seqdef_locdescr_psql_tbl:
            seqdef_locdescr_psql_tbl.delete_locus_description((f"{self._schemedict[self._scheme]['schemename_bigsdb']}_GeneCluster%",))
            for cluster, description in self._descriptiondict.items():
                # convert list to more meaningfull and aesthatically pleasing string
                descriptionstring = ' '.join(['Contains genes:', ', '.join([x for x in description])])
                seqdef_locdescr_psql_tbl.insert_locus_description((cluster, descriptionstring.replace('Contains genes:', ''), descriptionstring))

    def __recalculate_allele_designations(self, species: str) -> None:
        """
        Removes, recaculates and reinserts allele designations
        :param species: commonly used bioit species name: either genus or specific like stec.
        :return: None
        """
        with TblAlleleDesignations(species) as isolates_ad_psql_tbl, \
                TblEavText(species) as isolates_eavt_psql_tbl, \
                TblHistory(species) as isolates_history_psql_tbl:
            isolates_ad_psql_tbl.delete_designations((f"{self._schemedict[self._scheme]['schemename_bigsdb']}_GeneCluster%",))
            with TblEavTextHidden(species) as isolates_eavth_psql_tbl:
                listofsamplesandhits = isolates_eavth_psql_tbl.select_hidden((self._schemedict[self._scheme]['schemename_bigsdb'],))
            if len(listofsamplesandhits) > 0:
                for sampleandhits in listofsamplesandhits:
                    isolate_id: str = sampleandhits[0]
                    isolate_name: str = sampleandhits[2]
                    html_scheme_name = self._schemedict[self._scheme]['schemename_html']
                    report_url = UrlHelper.report_for_isolate(self._species, isolate_id, html_scheme_name)
                    if not self._scheme.endswith('vfdbcore') and not self._scheme.endswith('virulencefinder'):
                        self._eavhtmltable = '<style>table.nice { text-align: center; border-spacing:0 }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
                        self._eavhtmltable += f'<table class="data nice"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                        self._eavhtmltable += f'<tr align="left"><td colspan="4"><a href="{report_url}" target="_blank">Full report</a></td></tr>'
                    else:
                        self._eavhtmltable = f'<a href="{report_url}" target="_blank">Full report</a>'

                    clusterhitset = set()  # in case loci that were in different clusters at some point get in the same cluster
                    hits = json.loads(sampleandhits[1])
                    if len(hits) != 0:
                        for y in range(len(hits)):
                            hit = '_'.join([hits[y]['Accession'], hits[y]['Locus']])
                            if hit in self._clusterdict:
                                clusterhit = self._clusterdict[hit]
                                if not self._scheme.endswith('vfdbcore') and not self._scheme.endswith('virulencefinder'):
                                    self.___append_to_htmltable(hits[y], clusterhit)

                                if clusterhit not in clusterhitset:
                                    isolates_ad_psql_tbl.insert_designation_by_isolateid((clusterhit, isolate_id, '1'))
                                    clusterhitset.add(clusterhit)
                            else:
                                send_email(f"{hit} is not a valid key for self._clusterdict. The locus {hits[y]['Locus']} was found in isolate {isolate_name}\nCheck if it's due to the update of {self._scheme}",
                                           f"{Path(__file__).name} issue on host {socket.gethostname()}", dont_send_email=self._dont_send_email)

                    self._eavhtmltable += f'</table>'
                    isolates_eavt_psql_tbl.delete_eav(
                        (isolate_id, self._schemedict[self._scheme]['schemename_bigsdb']))
                    isolates_eavt_psql_tbl.insert_eav_id(
                        (isolate_id, self._schemedict[self._scheme]['schemename_bigsdb'], self._eavhtmltable))
                    isolates_history_psql_tbl.insert_history_id(
                        (isolate_id, 'Gene detection results reevaluated after database update'))

    @staticmethod
    def ___get_report_name_from_mongo(samplename: str, species: str) -> Union[str, Path]:
        """
        Get the name of the html report for the given isolate
        :param samplename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec.
        :return: report name for the isolate
        """
        mongoinit = MongoInitialisation(species=species, mongo_config_data=get_mongodb_config_data(), selected_connection_string='CONNECTION_STRING_AZURE')
        isolates_collection, _, _, _, _ = mongoinit.initialise_collections()
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

    GeneDetectionIntoPsql(args.species, args.do_not_recalculate)
