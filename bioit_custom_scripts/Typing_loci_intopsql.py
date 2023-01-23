import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List

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
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        schemedict: Dict[Dict[str, str]] = bigsdb_config_data['species'][species]['typing_schemes']
        for scheme in schemedict:
            if schemedict[scheme].get('dirdb') and schemedict[scheme]['dirdb'] != '':
                dirs: List[str] = next(os.walk(schemedict[scheme]['dirdb']))[1]
                for directory in dirs:
                    if not directory.startswith('.') and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_nucl' and (directory != 'fHbp_allele' and directory != 'fHbp_DNAfrag_Pasteur')) and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_pept' and (directory == 'fHbp_allele' or directory == 'fHbp_DNAfrag_Pasteur')):
                        sqlquery = """SELECT COUNT(*) FROM loci WHERE id=%s;"""
                        cur_seqdef.execute(sqlquery, (directory,))
                        present: List[List[int]] = cur_seqdef.fetchall()
                        if present[0][0] == 0:
                            logging.info(f"locus {directory} not present in loci")
                            sqlquery = """
                                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) 
                                       VALUES(%s, 'DNA', 'text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                            cur_seqdef.execute(sqlquery, (directory,))
                            sqlquery = """
                                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
                            cur_seqdef.execute(sqlquery, (schemedict[scheme]['schemename_bigsdb'], directory))
                            sqlquery = """
                                       INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) 
                                       VALUES(1, %s, 1, (SELECT CURRENT_DATE));"""
                            cur_seqdef.execute(sqlquery, (directory,))

                            # insert into isolates
                            dbaseurl: str = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{species}_seqdef',
                                                '&page=alleleInfo&locus=', f"{directory}", '&allele_id=[?]'])
                            sqlquery = """
                                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, 
                                       url, isolate_display, main_display, query_field, analysis, submission_template, 
                                       curator, date_entered, datestamp) 
                                       VALUES(%s, 'DNA', 'text', 't', 't', %s, %s, 
                                       %s, 'allele_only', 'f', 't', 't', 'f', 
                                       1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                            cur_isolates.execute(sqlquery, (directory, f'bigsdb_{species}_seqdef', directory, dbaseurl))
                            sqlquery = """
                                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
                            cur_isolates.execute(sqlquery, (schemedict[scheme]['schemename_bigsdb'], directory))
                        elif present[0][0] == 1:
                            sqlquery = """
                                       SELECT count(*) FROM scheme_members WHERE scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""
                            cur_seqdef.execute(sqlquery, (schemedict[scheme]['schemename_bigsdb'], directory))
                            present2: List[List[int]] = cur_seqdef.fetchall()
                            if present2[0][0] == 0:
                                logging.info(f"locus {directory} not present in scheme members")
                                # add into seqdef scheme members
                                sqlquery_members = """
                                                   INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                                                   VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
                                cur_seqdef.execute(sqlquery_members, (schemedict[scheme]['schemename_bigsdb'], directory))
                                cur_isolates.execute(sqlquery_members, (schemedict[scheme]['schemename_bigsdb'], directory))
                            else:
                                continue
                        else:
                            continue
        DatabaseConnection().close_connections(con_isolates, con_seqdef)

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