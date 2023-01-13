import argparse
import logging
import os
import sys

import psycopg2
import yaml

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.config import BIGSDB_CONFIG


def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=specieslist, default=specieslist,
                                 nargs='+')  # this does allow for the same species multiple times but doesnt really matter
    return argument_parser.parse_args()


def _insert_loci() -> None:
    """
    Main function to insert all loci for the given species
    :return:
    """
    for species in list(set(args.species)):
        con_seqdef = psycopg2.connect(database=f"{config_data['species'][species]['seqdefdb']}", user="apache", password=config_data.get('postgresql_apache_pass'),
                               host="127.0.0.1", port="")
        con_seqdef.autocommit = True
        cur_seqdef = con_seqdef.cursor()
        con_isolates = psycopg2.connect(database=f"{config_data['species'][species]['isolatesdb']}", user="apache", password=config_data.get('postgresql_apache_pass'),
                                        host="127.0.0.1", port="")
        con_isolates.autocommit = True
        cur_isolates = con_isolates.cursor()

        schemedict = config_data['species'][species]['typing_schemes']
        for scheme in schemedict.keys():
            if schemedict[scheme].get('dirdb') and schemedict[scheme]['dirdb'] != '':
                dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
                for dir in dirs:
                    if not dir.startswith('.') and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (schemedict[scheme]['schemename_bigsdb'] == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
                        cur_seqdef.execute(f"SELECT COUNT(*) FROM loci WHERE id='{dir}'")
                        present = cur_seqdef.fetchall()
                        if present[0][0] == 0:
                            print(f"locus {dir} not present in loci")
                            sqlquery = """
                                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) 
                                       VALUES(%s, 'DNA', 'text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                            cur_seqdef.execute(sqlquery, (dir))
                            sqlquery = """
                                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
                            cur_seqdef.execute(sqlquery, (schemedict[scheme]['schemename_bigsdb'], dir))
                            sqlquery = """
                                       INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) 
                                       VALUES(1, %s, 1, (SELECT CURRENT_DATE));"""
                            cur_seqdef.execute(sqlquery, (dir))

                            # insert into isolates
                            dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{species}_seqdef',
                                                '&page=alleleInfo&locus=', f"{dir}", '&allele_id=[?]'])
                            sqlquery = """
                                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, 
                                       url, isolate_display, main_display, query_field, analysis, submission_template, 
                                       curator, date_entered, datestamp) 
                                       VALUES(%s, 'DNA', 'text', 't', 't', %s, %s, 
                                       %s, 'allele_only', 'f', 't', 't', 'f', 
                                       1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                            cur_isolates.execute(sqlquery, (dir, f'bigsdb_{species}_seqdef', dir, dbaseurl))
                            sqlquery = """
                                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
                            cur_isolates.execute(sqlquery, (schemedict[scheme]['schemename_bigsdb'], dir))
                        elif present[0][0] == 1:
                            sqlquery = """
                                       SELECT count(*) FROM scheme_members WHERE scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""
                            cur_seqdef.execute(sqlquery, (schemedict[scheme]['schemename_bigsdb'], dir))
                            present2 = cur_seqdef.fetchall()
                            if present2[0][0] == 0:
                                print(f"locus {dir} not present in scheme members")
                                # add into seqdef scheme members
                                sqlquery_members = """
                                           INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                                           VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
                                cur_seqdef.execute(sqlquery_members, (schemedict[scheme]['schemename_bigsdb'], dir))
                                cur_isolates.execute(sqlquery_members, (schemedict[scheme]['schemename_bigsdb'], dir))
                            else:
                                continue
                        else:
                            continue
        con_seqdef.close()
        cur_isolates.close()

if __name__ == '__main__':

    # Read the global config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(config_data['species'].keys()))

    # execute script
    _insert_loci()

    # this script does not need to send mails because it does not run multiple times, nor automatically, only through Ansible once