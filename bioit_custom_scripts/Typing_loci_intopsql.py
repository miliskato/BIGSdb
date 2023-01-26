import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from bioit_custom_scripts.components.python_utility_functions import get_bigsdb_config_data


def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=specieslist, default=specieslist,
                                 nargs='+')  # this does allow for the same species multiple times but doesnt really matter, theyre uniquely filtered using set()
    return argument_parser.parse_args()


def _insert_loci() -> None:
    """
    Main function to insert all loci for the given species
    :return: None
    """
    for species in set(args.species):
        with DatabaseConnection(species, 'isolates') as isolates_psql_db, DatabaseConnection(species, 'seqdef') as seqdef_psql_db:
            schemedict: Dict[str, Dict[str, str]] = bigsdb_config_data['species'][species]['typing_schemes']
            for scheme in schemedict:
                if schemedict[scheme].get('dirdb') and schemedict[scheme]['dirdb'] != '':
                    dirs: List[str] = next(os.walk(schemedict[scheme]['dirdb']))[1]
                    for directory in dirs:
                        if not directory.startswith('.') and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_nucl' 
                                                                  and (directory != 'fHbp_allele' and directory != 'fHbp_DNAfrag_Pasteur')) \
                                and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_pept' and (directory == 'fHbp_allele' 
                                                                                                     or directory == 'fHbp_DNAfrag_Pasteur')):
                            present: List[Tuple[int]] = seqdef_psql_db.execute_query(DatabaseConnection.UNI_SEL_COUNT_TB_LOCI_VAR_LOCUS, (directory,))
                            if present[0][0] == 0:
                                logging.info(f"locus {directory} not present in loci")
                                seqdef_psql_db.execute_query(DatabaseConnection.SEQ_INS__TB_LOCI_VAR_LOCUS, (directory,))
                                seqdef_psql_db.execute_query(DatabaseConnection.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS,
                                                             (schemedict[scheme]['schemename_bigsdb'], directory))
                                seqdef_psql_db.execute_query(DatabaseConnection.SEQ_INS__TB_CLDBLOCI_VAR_LOCUS, (directory,))
    
                                # insert into isolates
                                dbaseurl: str = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{species}_seqdef',
                                                    '&page=alleleInfo&locus=', f"{directory}", '&allele_id=[?]'])
                                isolates_psql_db.execute_query(DatabaseConnection.ISO_INS__TB_LOCI_VAR_LOCUS_DBNAME_DBID_URL,
                                                               (directory, f'bigsdb_{species}_seqdef', directory, dbaseurl))
                                isolates_psql_db.execute_query(DatabaseConnection.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS,
                                                               (schemedict[scheme]['schemename_bigsdb'], directory))
                            elif present[0][0] == 1:
                                present2: List[Tuple[int]] = seqdef_psql_db.execute_query(DatabaseConnection.UNI_SEL_COUNT_TB_SCHMEM_VAR_SCHEME_LOCUS,
                                                             (schemedict[scheme]['schemename_bigsdb'], directory))
                                if present2[0][0] == 0:
                                    logging.info(f"locus {directory} not present in scheme members")
                                    # add into seqdef scheme members
                                    seqdef_psql_db.execute_query(DatabaseConnection.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS,
                                                                 (schemedict[scheme]['schemename_bigsdb'], directory))
                                    isolates_psql_db.execute_query(DatabaseConnection.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS,
                                                                   (schemedict[scheme]['schemename_bigsdb'], directory))
                                else:
                                    continue
                            else:
                                continue


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    # execute script
    _insert_loci()

    # this script does not need to send mails because it does not run multiple times, nor automatically, only through Ansible once