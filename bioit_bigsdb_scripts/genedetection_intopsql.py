import argparse
import logging
import socket
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Union

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql.gene_detection_profiles_batch_inserter import GeneDetectionProfilesBatchData, GeneDetectionProfilesBatchInserter
from bioit_bigsdb_scripts.inserters.context.gene_detection_context import GeneDetectionContext
from bioit_bigsdb_scripts.inserters.context.gene_detection_context_builder_factory import GeneDetectionContextBuilderFactory
from bioit_bigsdb_scripts.components.psql import TblLocusDescriptions, TblLoci, TblSchemes
from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data, send_email


def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', type=str, choices=specieslist)
    return argument_parser.parse_args()


class GeneDetectionIntoPsql:
    """
    Class containing function to insert gene detection loci and alleles and update them
    """

    def __init__(self, species: str, dont_send_email: bool = False) -> None:
        """
        Initialises this class and executes the main function: _gene_detection_insertion_and_recalculation
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param dont_send_email: do not send emails, only log
        :return: None
        """
        self._species = species
        self._dont_send_email = dont_send_email
        self._bigsdb_config_data = get_bigsdb_config_data()

    def insert_schemes(self) -> None:
        """
        Inserts schemes into BIGSdb databases
        :return: None
        """
        try:
            scheme_dict: Dict[str, Any] = self._bigsdb_config_data['species'][self._species].get('genedetection_schemes')
            self._gene_detection_insertion_and_recalculation(self._species, scheme_dict)

        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

    def _gene_detection_insertion_and_recalculation(self, species: str, scheme_dict: Union[Dict[str, Any], None]) -> None:
        """
        Inserts gene detection loci and alleles and recalculates existing loci/alleles
        Recalculation pertains the Clusters which are recalculated weekly on often 80% identity
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param scheme_dict: bigsdb config for the scheme
        :return: None
        """
        if scheme_dict is None:
            return

        context_builder_factory = GeneDetectionContextBuilderFactory()

        for scheme, scheme_config in scheme_dict.items():
            context = context_builder_factory.build(scheme, scheme_config)
            self.__insert_loci_and_alleles(species, context)
            self.__update_locus_descriptions(species, context)

    def __insert_loci_and_alleles(self, species: str, context: GeneDetectionContext) -> None:
        """
        Inserts all the loci (clusters), scheme members and alleles (0/1) which are not already in seqdef and isolate dbs
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param context: GeneDetectionContext object
        :return: None
        """
        scheme = context.scheme_config['schemename_bigsdb']
        client_db_id = f'bigsdb_{self._species}_seqdef'
        dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{self._species}_seqdef', '&page=alleleInfo&locus=', f"{scheme}", '&allele_id=[?]'])

        with TblSchemes(species, 'seqdef') as seqdef_schemes_psql_tbl, \
                TblLoci(self._species, 'seqdef') as seqdef_loci_psql_tbl:

            seqdef_scheme_id = int(seqdef_schemes_psql_tbl.select_scheme_id_based_on_scheme_name((scheme,))[0][0])
            present = seqdef_loci_psql_tbl.get_locus_list_for_this_scheme((scheme,))

        cluster_list = [x for x in list(context.description_dict.keys()) if x not in present]
        if len(cluster_list) == 0:
            return

        batch_data = GeneDetectionProfilesBatchData()
        for cluster in cluster_list:
            date_string = str(date.today())
            batch_data.loci_fields.append((cluster, 'DNA', 'text', 't', 't', 1, date_string, date_string))
            batch_data.scheme_members_fields.append((seqdef_scheme_id, cluster, 1, date_string))
            batch_data.client_dbase_loci_fields.append((1, cluster, 1, date_string))
            batch_data.isolates_loci_fields.append(
                (cluster, 'DNA', 'text', 't', 't', client_db_id, cluster, dbaseurl, 'allele_only', 'f', 't', 't', 'f', 1, date_string, date_string))
            batch_data.sequences_fields.append((cluster, '1', 'dummy1', 'unchecked', 1, 1, date_string, date_string))
            batch_data.sequences_fields.append((cluster, '0', 'null allele', 'unchecked', 1, 1, date_string, date_string))

        with GeneDetectionProfilesBatchInserter(self._species) as batch_inserter:
            batch_inserter.insert(batch_data)

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

    GeneDetectionIntoPsql(args.species).insert_schemes()
