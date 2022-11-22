import os
import psycopg2
import argparse
import logging
import yaml
import sys

from config import BIGSDB_CONFIG


def _parse_arguments(speciesdict) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=list(speciesdict.keys()), default=list(speciesdict.keys()),
                                 nargs='+')  # this does allow for the same species multiple times but doesnt really matter
    return argument_parser.parse_args()


def _insert_loci():
    for species in list(set(args.species)):
        con_seqdef = psycopg2.connect(database=f"{config_data['species'][species]['seqdefdb']}", user="apache", password="remote",
                               host="127.0.0.1", port="")
        con_seqdef.autocommit = True
        cur_seqdef = con_seqdef.cursor()
        con_isolates = psycopg2.connect(database=f"{config_data['species'][species]['isolatesdb']}", user="apache", password="remote",
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
                            # add into seqdef loci
                            cur_seqdef.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                              VALUES('{dir}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                            # add into seqdef scheme members
                            cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                              VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
                            cur_seqdef.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                              VALUES(1, '{dir}', 1, (SELECT CURRENT_DATE))")
                            # If it doesnt exist in seqdef loci, then normally not in isolate loci aswell
                            dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f"{schemedict[scheme]['seqdefdb']}", '&page=alleleInfo&locus=', f"{dir}", '&allele_id=[?]'])
                            cur_isolates.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                                        f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                                        f"curator, date_entered, datestamp) \
                                              VALUES('{dir}','DNA','text', 't', 't', '{schemedict[scheme]['seqdefdb']}', '{dir}', "
                                        f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                                        f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                            # add into isolate scheme members
                            cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                              VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
                        elif present[0][0] == 1:
                            cur_seqdef.execute(f"SELECT count(*) FROM scheme_members WHERE locus='{dir}' and scheme_id=(SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}')")
                            present2 = cur_seqdef.fetchall()
                            if present2[0][0] == 0:
                                print(f"locus {dir} not present in scheme members")
                                # add into seqdef scheme members
                                cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                  VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
                                cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                  VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{dir}', 1, (SELECT CURRENT_DATE))")
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
    args = _parse_arguments(config_data['species'])

    # execute script
    _insert_loci()

    # this script does not need to send mails because it does not run multiple times, nor automatically, only through Ansible once