import argparse
import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Dict, List

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblLoci, TblSchemeMembers, TblClientDbaseLoci
from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data, send_email


def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=MongoConfigProvider.get_currently_supported_species())
    return argument_parser.parse_args()


class TypingLociIntoPsql:
    """
    Class containing function to insert typing loci into psql
    """

    def __init__(self, species: str, dont_send_email: bool = False) -> None:
        """
        Initialises this class and executes the main function: _insert_loci
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param dont_send_email: do not send emails, only log
        :return: None
        """
        self._species = species
        self._dont_send_email = dont_send_email

        self._bigsdb_config_data = get_bigsdb_config_data()

        try:
            self._insert_loci()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

    def _insert_loci(self) -> None:
        """
        Main function to insert all loci for the given species
        :return: None
        """
        with TblLoci(self._species, 'isolates') as isolates_loci_psql_tbl, \
                TblLoci(self._species, 'seqdef') as seqdef_loci_psql_tbl, \
                TblSchemeMembers(self._species, 'isolates') as isolates_schememembers_psql_tbl, \
                TblSchemeMembers(self._species, 'seqdef') as seqdef_schememembers_psql_tbl, \
                TblClientDbaseLoci(self._species) as seqdef_clientdbaseloci_psql_tbl:
            schemedict: Dict[str, Dict[str, str]] = self._bigsdb_config_data['species'][self._species]['typing_schemes']
            if schemedict is None:
                return
            for scheme in schemedict:
                if schemedict[scheme].get('dirdb') and schemedict[scheme]['dirdb'] != '':
                    bigsdb_scheme_name = schemedict[scheme]['schemename_bigsdb']
                    dirs: List[str] = next(os.walk(schemedict[scheme]['dirdb']))[1]
                    dirs = [x for x in dirs if not x.startswith('.')]

                    for directory in dirs:
                        if (bigsdb_scheme_name == 'fHbp_nucl' and (directory not in ['fHbp_allele', 'fHbp_DNAfrag_Pasteur'])) \
                                or (bigsdb_scheme_name == 'fHbp_pept' and (directory in ['fHbp_allele', 'fHbp_DNAfrag_Pasteur'])):
                            continue

                        present = seqdef_loci_psql_tbl.count_locus((directory,))
                        if present[0][0] == 0:
                            logging.info(f"locus {directory} not present in loci")
                            seqdef_loci_psql_tbl.insert_locus_seqdef((directory,))
                            seqdef_schememembers_psql_tbl.insert_scheme_member((bigsdb_scheme_name, directory))
                            seqdef_clientdbaseloci_psql_tbl.insert_locus((directory,))

                            # insert into isolates
                            dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{self._species}_seqdef',
                                                '&page=alleleInfo&locus=', f"{directory}", '&allele_id=[?]'])
                            isolates_loci_psql_tbl.insert_locus_isolates((directory, f'bigsdb_{self._species}_seqdef', directory, dbaseurl))
                            isolates_schememembers_psql_tbl.insert_scheme_member(
                                (bigsdb_scheme_name, directory))
                        elif present[0][0] == 1:
                            present2 = seqdef_schememembers_psql_tbl.count_scheme_member(
                                (bigsdb_scheme_name, directory))
                            if present2[0][0] == 0:
                                logging.info(f"locus {directory} not present in scheme members")
                                # add into seqdef scheme members
                                seqdef_schememembers_psql_tbl.insert_scheme_member(
                                    (bigsdb_scheme_name, directory))
                                isolates_schememembers_psql_tbl.insert_scheme_member(
                                    (bigsdb_scheme_name, directory))


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments()

    # execute script
    TypingLociIntoPsql(args.species)
