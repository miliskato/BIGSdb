import argparse
import csv
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


class GeneDetectionContext:
    """Class to create the context for the scheme of interest"""

    def __init__(self, scheme: str, scheme_config: Dict[str, Any]) -> None:
        """
        :param scheme: name of the scheme
        :param scheme_config: config from bigsdb config file for this scheme
        :return: None
        """
        self.scheme = scheme
        self.description_dict: Dict[str, List[str]] = {}
        self.cluster_dict: Dict[str, str] = {}
        self.scheme_config = scheme_config

    def add_description(self, gene_cluster: str, description: str) -> None:
        """
        Fills in dict with gene_cluster_name as keys and description of the gene_cluster (alleles/mutations) as values
        :param gene_cluster: gene cluster name
        :param description: description of the gene cluster components
        :return: None
        """
        if not self.description_dict.get(gene_cluster):
            self.description_dict[gene_cluster] = []
        self.description_dict[gene_cluster].append(description)

    def set_sequence_genecluster_name(self, sequence_id: str, bigsdb_genecluster_name: str) -> None:
        """
        Fills in dict with sequence_id as key and combination of bigsdb scheme name and gene cluster name as values
        :param sequence_id: sequence id
        :param bigsdb_genecluster_name: gene cluster name
        :return: None
        """
        self.cluster_dict[sequence_id] = bigsdb_genecluster_name


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

    def insert_schemes(self) -> None:
        """
        Inserts schemes into BIGSdb seqdef database
        :return: None
        """
        try:
            for species in set(self._species_list):
                scheme_dict: Dict[str, Any] = self._bigsdb_config_data['species'][species].get('genedetection_schemes')
                self._gene_detection_insertion_and_recalculation(species, scheme_dict)

        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

    def _gene_detection_insertion_and_recalculation(self, species: str, scheme_dict: Union[Dict[str, Any], None]) -> None:
        """
        Inserts gene detection loci and alleles and recalculates existing loci/alleles
        Recalculation pertains the Clusters which are recalculated weekly on often 80% identity
        :param species: commonly used bioit species name: either genus or specific like stec.
        :return: None
        """
        if scheme_dict is None:
            return

        for scheme in scheme_dict:
            scheme_config = scheme_dict[scheme]
            context = self.create_gene_detection_context(scheme, scheme_config)
            self.__insert_loci_and_alleles(species, context)
            self.__update_locus_descriptions(species, context)

            if not self._do_not_recalculate:
                self.__recalculate_allele_designations(species, context)

    @staticmethod
    def create_gene_detection_context(scheme: str, scheme_config: Any) -> GeneDetectionContext:
        """
        Creates the necessary dictionaries for the current version of the database
        :return: GeneDetectionContext object
        """
        if scheme_config['schemename_bigsdb'] == 'ResFinder4':
            return GeneDetectionIntoPsql._create_resfinder4_gene_detection_context(scheme, scheme_config)
        else:
            return GeneDetectionIntoPsql._create_generic_gene_detection_context(scheme, scheme_config)

    @staticmethod
    def _create_resfinder4_gene_detection_context(scheme: str, scheme_config: Dict[str, Any]) -> GeneDetectionContext:
        """
        Based on "phenotypes.txt" file from ResFinder4, create dictionaries used to insert loci in seqdef
        :param scheme: name of the scheme
        :param scheme_config: bigsdb config for this scheme
        :return: GeneDetectionContext object
        """
        context = GeneDetectionContext(scheme, scheme_config)
        with Path(scheme_config['metadatafile']).open('r') as phenotypes:
            file_reader = csv.DictReader(phenotypes, delimiter="\t")
            for row in file_reader:
                gene_accession = row.get('Gene_accession no.')

                if len(gene_accession.split("_")) == 3:
                    gene, _, accession = gene_accession.split("_")
                else:
                    gene = gene_accession.split("_")[0]
                    accession = "_".join((gene_accession.split("_")[2], gene_accession.split("_")[3]))
                bigsdb_genecluster_name = f"{scheme_config['schemename_bigsdb']}_{gene}"

                sequence_id = "_".join([gene, accession])
                context.set_sequence_genecluster_name(sequence_id, bigsdb_genecluster_name)
                context.add_description(bigsdb_genecluster_name, accession)
        return context

    @staticmethod
    def _create_generic_gene_detection_context(scheme: str, scheme_config: Dict[str, Any]) -> GeneDetectionContext:
        """
        Based on metadata file (json like) of the scheme, create dictionaries used to insert loci in seqdef
        :param scheme: name of the scheme
        :param scheme_config: bigsdb config for this scheme
        :return: GeneDetectionContext object
        """

        context = GeneDetectionContext(scheme, scheme_config)
        with Path(scheme_config['metadatafile']).open('r') as handle:
            sequencedictlist: Dict[str, Dict[str, Any]] = json.load(handle)
            # sequence id must be based on accession and allele/mutation because some schemes have duplicate accession numbers
            for sequencename in sequencedictlist:
                sequence_details = sequencedictlist[sequencename]
                if sequence_details['accession'] is None:
                    sequence_details['accession'] = "-"

                bigsdb_scheme_name = scheme_config['schemename_bigsdb']
                bigsdb_genecluster_name = f"{bigsdb_scheme_name}_Gene{sequence_details['cluster']}"

                context.set_sequence_genecluster_name(GeneDetectionIntoPsql._create_sequence_id(sequence_details),
                                                      bigsdb_genecluster_name)

                key = 'allele' if bigsdb_scheme_name != 'VFDB_core' else 'gene'
                value = (sequence_details[key]).replace("'", "")
                context.add_description(key, value)

        return context

    @staticmethod
    def _create_sequence_id(sequence_details: Dict[str, any]) -> str:
        """
        Generate the sequence_id which is a jonction of accession and allele items
        :param sequence_details: dictionary containing the details of the sequences
        :return: sequence_id
        """
        return '_'.join([(sequence_details['accession']), (sequence_details['allele']).replace("'", "")])

    def __insert_loci_and_alleles(self, species: str, context: GeneDetectionContext) -> None:
        """
        Inserts all the loci (clusters), scheme members and alleles (dummy boolean) in seqdef and isolate dbs if they are not
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param context: GeneDetectionContext object
        :return: None
        """
        json_superclass_instance = JsonSuperClass('dummyname', species,
                                                  JsonReportDict({'dummydictkey': 'dummydictvalue'}),
                                                  config_data=self._bigsdb_config_data)
        with TblSequences(species) as seqdef_sequences_psql_tbl, TblLoci(species, 'seqdef') as seqdef_loci_psql_tbl:
            for cluster in context.description_dict.keys():
                present: List[Tuple[int]] = seqdef_loci_psql_tbl.count_locus((cluster,))
                if present[0][0] == 0:
                    json_superclass_instance.insert_locus_if_needed(cluster, context.scheme_config['schemename_bigsdb'])
                    seqdef_sequences_psql_tbl.insert_sequence((cluster, '1', 'dummy1'))
                    seqdef_sequences_psql_tbl.insert_sequence((cluster, '0', 'null allele'))
                else:
                    continue

    @staticmethod
    def __update_locus_descriptions(species: str, context: GeneDetectionContext) -> None:
        """
        Updates the locus descriptions to the new database version
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param context: GeneDetectionContext object
        :return: None
        """
        with TblLocusDescriptions(species) as seqdef_locdescr_psql_tbl:
            seqdef_locdescr_psql_tbl.delete_locus_description((f"{context.scheme_config['schemename_bigsdb']}_%",))
            for cluster, description in context.description_dict.items():
                # convert list to more meaningfull and aesthatically pleasing string
                description_string = ' '.join(['Contains genes:', ', '.join([x for x in description])])
                seqdef_locdescr_psql_tbl.insert_locus_description(
                    (cluster, description_string.replace('Contains genes:', ''), description_string))

    def __recalculate_allele_designations(self, species: str, context: GeneDetectionContext) -> None:
        """
        Removes, recalculates and reinserts allele designations
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param context: GeneDetectionContext object
        :return: None
        """
        with TblAlleleDesignations(species) as isolates_ad_psql_tbl, \
                TblEavText(species) as isolates_eavt_psql_tbl, \
                TblHistory(species) as isolates_history_psql_tbl:
            isolates_ad_psql_tbl.delete_designations((f"{context.scheme_config['schemename_bigsdb']}_%",))
            with TblEavTextHidden(species) as isolates_eavth_psql_tbl:
                listofsamplesandhits = isolates_eavth_psql_tbl.select_hidden(
                    (context.scheme_config['schemename_bigsdb'],))
            if len(listofsamplesandhits) > 0:
                for sampleandhits in listofsamplesandhits:
                    eavhtmltable = ''

                    isolate_id: str = sampleandhits[0]
                    isolate_name: str = sampleandhits[2]
                    html_scheme_name = context.scheme_config['schemename_html']
                    report_url = UrlHelper.report_for_isolate(species, isolate_id, html_scheme_name)
                    if not context.scheme.endswith('vfdbcore') and not context.scheme.endswith('virulencefinder'):
                        eavhtmltable += '<style>table.nice { text-align: center; border-spacing:0 }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
                        eavhtmltable += f'<table class="data nice"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                        eavhtmltable += f'<tr align="left"><td colspan="4"><a href="{report_url}" target="_blank">Full report</a></td></tr>'
                    else:
                        eavhtmltable += f'<a href="{report_url}" target="_blank">Full report</a>'

                    clusterhitset = set()  # in case loci that were in different clusters at some point get in the same cluster
                    hits = json.loads(sampleandhits[1])
                    if len(hits) != 0:
                        for y in range(len(hits)):
                            hit = '_'.join([hits[y]['Accession'], hits[y]['Locus']])
                            if hit in context.cluster_dict:
                                clusterhit = context.cluster_dict[hit]
                                if not context.scheme.endswith('vfdbcore') and not context.scheme.endswith(
                                        'virulencefinder'):
                                    eavhtmltable += GeneDetectionIntoPsql.create_gene_locus_row(hits[y], clusterhit)

                                if clusterhit not in clusterhitset:
                                    isolates_ad_psql_tbl.insert_designation_by_isolateid((clusterhit, isolate_id, '1'))
                                    clusterhitset.add(clusterhit)
                            else:
                                send_email(
                                    f"{hit} is not a valid key for self._clusterdict. The locus {hits[y]['Locus']} was found in isolate {isolate_name}\nCheck if it's due to the update of {context.scheme}",
                                    f"{Path(__file__).name} issue on host {socket.gethostname()}",
                                    dont_send_email=self._dont_send_email)

                    eavhtmltable += f'</table>'
                    isolates_eavt_psql_tbl.delete_eav((isolate_id, context.scheme_config['schemename_bigsdb']))
                    isolates_eavt_psql_tbl.insert_eav_id(
                        (isolate_id, context.scheme_config['schemename_bigsdb'], eavhtmltable))
                    isolates_history_psql_tbl.insert_history_id(
                        (isolate_id, 'Gene detection results reevaluated after database update'))


    @staticmethod
    def create_gene_locus_row(hit: Dict[str, str], clusterhit: str) -> str:
        """
        Creates a line to add to the html table
        :param hit: hit dictionary
        :param clusterhit: current cluster of the hit
        :return: html code corresponding to a new line for the results table
        """
        # append Cluster
        gene_cluster = clusterhit.split('Cluster_')[1]
        locus_name: str = hit['Locus']

        return f'<tr><td>{gene_cluster}</td><td>{locus_name}</td></tr>'


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    GeneDetectionIntoPsql(args.species, args.do_not_recalculate).insert_schemes()
