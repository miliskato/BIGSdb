# This script calculates all isolates with similar cgMLST profiles

""""
Deprecated, if ever to be used some work to do including psycopg2 sanitization
"""
import argparse
import os
import sys
from pathlib import Path

import psycopg2
import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.databaseconnection import DatabaseConnection
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data

dirdict = {
          'mycobacterium': '/db/sequence_typing/mycobacterium/cgmlst',
          'listeria': '/db/sequence_typing/listeria/cgmlst',
          'neisseria': '/db/sequence_typing/neisseria/cgmlst',
          'stec': '/db/sequence_typing/ecoli/cgmlst',
          'salmonella': '/db/sequence_typing/salmonella/cgmlst'
          }


argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--species', required=True, type=str, choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
argument_parser.add_argument('--isolatename', required=True, type=str)
args = argument_parser.parse_args()
species = args.species
isolate_name = args.isolatename


bigsdb_config_data = get_bigsdb_config_data()

(con_isolates, isolates_psql_db), (con_seqdef, seqdef_psql_db) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

isolates_psql_db.execute_query(f"SELECT id FROM isolates")
listofsamples = isolates_psql_db.fetchall()

isolates_psql_db.execute_query(f"SELECT id FROM isolates WHERE isolate='{isolate_name}'")
isolate_id = isolates_psql_db.fetchall()[0][0]

isolates_psql_db.execute_query(f"SELECT field FROM eav_fields WHERE field LIKE 'cgMLST_differences_%'")
differencefields = isolates_psql_db.fetchall()

for isolate_id_from_comparison in listofsamples:
    dirs = next(os.walk(dirdict[species]))[1]
    different_count = 0
    for dir in dirs:
        if not dir.startswith('.'):
            isolates_psql_db.execute_query(f"SELECT allele_id FROM allele_designations WHERE isolate_id='{isolate_id_from_comparison[0]}' AND locus='{dir}'")
            isolate1result = isolates_psql_db.fetchall()
            isolates_psql_db.execute_query(f"SELECT allele_id FROM allele_designations WHERE isolate_id=(SELECT id FROM isolates WHERE isolate='{isolate_name}') AND locus='{dir}'")
            isolateXresult = isolates_psql_db.fetchall()
            if isolate1result == isolateXresult:
                continue
            else:
                different_count+=1
    for field in differencefields:
        interval = field[0].split('_')[-1]
        interval_start = interval.split('-')[0]
        interval_stop = interval.split('-')[-1]
        print(different_count, isolate_id_from_comparison)
        if different_count >= int(interval_start) and different_count <= int(interval_stop):
            isolates_psql_db.execute_query(f"SELECT isolate FROM isolates WHERE id='{isolate_id_from_comparison[0]}'")
            isolate_name_from_comparison=isolates_psql_db.fetchall()[0][0]
            # to insert
            isolates_psql_db.execute_query(f"SELECT value FROM eav_text WHERE isolate_id=(SELECT id FROM isolates WHERE isolate='{isolate_name}') and field='{field[0]}'")
            present = isolates_psql_db.fetchall()
            # if table absent in new sample
            print(present)
            if present == []:
                eavhtmltable = '<table class="data"><tr><th>Isolate id</th><th>Isolate</th></tr></table>'
                eavhtmltable = eavhtmltable.replace('</table>', ''.join(['<tr><td>', str(isolate_id_from_comparison[0]), '</td>', '<td>', isolate_name_from_comparison, '</td></tr>', '</table>']))
                isolates_psql_db.execute_query(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                            f"'{field[0]}', '{eavhtmltable}') ")
                isolates_psql_db.execute_query(f"SELECT value FROM eav_text WHERE isolate_id='{isolate_id_from_comparison[0]}' and field='{field[0]}'")
                present2 = isolates_psql_db.fetchall()
                # table is absent in comparison sample
                if present2 == []:
                    eavhtmltable2 = '<table class="data"><tr><th>Isolate id</th><th>Isolate</th></tr></table>'
                    eavhtmltable2 = eavhtmltable2.replace('</table>', ''.join(['<tr><td>', str(isolate_id), '</td>', '<td>', isolate_name, '</td></tr>', '</table>']))
                    isolates_psql_db.execute_query(f"INSERT INTO eav_text(isolate_id, "
                                f"field, value)"
                                f"VALUES('{isolate_id_from_comparison[0]}',"
                                f"'{field[0]}', '{eavhtmltable2}') ")
                # table is present in comparison sample
                else:
                    isolates_psql_db.execute_query(f"SELECT value FROM eav_text WHERE isolate_id='{isolate_id_from_comparison[0]}' and field='{field[0]}'")
                    eavhtmltable2 = isolates_psql_db.fetchall()[0][0]
                    if ''.join(['<td>', isolate_name, '</td>']) in eavhtmltable2:
                        continue
                    else:
                        eavhtmltable2 = eavhtmltable2.replace('</table>', ''.join(['<tr><td>', str(isolate_id), '</td>', '<td>', isolate_name, '</td></tr>', '</table>']))
                        isolates_psql_db.execute_query(f"DELETE FROM eav_text WHERE isolate_id='{isolate_id_from_comparison[0]}' and field='{field[0]}'")
                        isolates_psql_db.execute_query(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES('{isolate_id_from_comparison[0]}',"
                                    f"'{field[0]}', '{eavhtmltable2}') ")

            # table is present in new sample
            else:
                isolates_psql_db.execute_query(f"SELECT value FROM eav_text WHERE isolate_id='{isolate_id}' and field='{field[0]}'")
                eavhtmltable = isolates_psql_db.fetchall()[0][0]
                print(eavhtmltable, ''.join(['<td>', isolate_name_from_comparison, '</td>']))
                if ''.join(['<td>', isolate_name_from_comparison, '</td>']) in eavhtmltable:
                    continue
                else:
                    eavhtmltable = eavhtmltable.replace('</table>', ''.join(['<tr><td>', str(isolate_id_from_comparison[0]), '</td>', '<td>', isolate_name_from_comparison, '</td></tr>', '</table>']))
                    isolates_psql_db.execute_query(f"DELETE FROM eav_text WHERE isolate_id='{isolate_id}' and field='{field[0]}'")
                    isolates_psql_db.execute_query(f"INSERT INTO eav_text(isolate_id, "
                                f"field, value)"
                                f"VALUES('{isolate_id}',"
                                f"'{field[0]}', '{eavhtmltable}') ")
                isolates_psql_db.execute_query(f"SELECT value FROM eav_text WHERE isolate_id='{isolate_id_from_comparison[0]}' and field='{field[0]}'")
                present2 = isolates_psql_db.fetchall()
                # table is absent in comparison sample
                if present2 == []:
                    eavhtmltable2 = '<table class="data"><tr><th>Isolate id</th><th>Isolate</th></tr></table>'
                    eavhtmltable2 = eavhtmltable2.replace('</table>', ''.join(['<tr><td>', str(isolate_id), '</td>', '<td>', isolate_name, '</td></tr>', '</table>']))
                    isolates_psql_db.execute_query(f"INSERT INTO eav_text(isolate_id, "
                                f"field, value)"
                                f"VALUES('{isolate_id_from_comparison[0]}',"
                                f"'{field[0]}', '{eavhtmltable2}') ")
                # table is present in comparison sample
                else:
                    isolates_psql_db.execute_query(f"SELECT value FROM eav_text WHERE isolate_id='{isolate_id_from_comparison[0]}' and field='{field[0]}'")
                    eavhtmltable2 = isolates_psql_db.fetchall()[0][0]
                    if ''.join(['<td>', isolate_name, '</td>']) in eavhtmltable2:
                        continue
                    else:
                        eavhtmltable2 = eavhtmltable2.replace('</table>', ''.join(['<tr><td>', str(isolate_id), '</td>', '<td>', isolate_name, '</td></tr>', '</table>']))
                        isolates_psql_db.execute_query(f"DELETE FROM eav_text WHERE isolate_id='{isolate_id_from_comparison[0]}' and field='{field[0]}'")
                        isolates_psql_db.execute_query(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES('{isolate_id_from_comparison[0]}',"
                                    f"'{field[0]}', '{eavhtmltable2}') ")
        else:
            continue