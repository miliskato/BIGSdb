import os
import sys
import psycopg2
import argparse
from pathlib import Path
import re

#leave dirdb empty for atypic typing schemes
schemedict = {'mycobacterium_mlst': {'dirdb': '/db/sequence_typing/mycobacterium/mlst', 'tsvname': 'mlst'},
              'mycobacterium_cgmlst': {'dirdb': '/db/sequence_typing/mycobacterium/cgmlst', 'tsvname': 'cgmlst'},
              'mycobacterium_spoligotyping': {'dirdb': '', 'tsvname': 'spoligotype_binary'},
              'mycobacterium_51SNPassay': {'dirdb': '', 'tsvname': '51SNP'},
              'mycobacterium_csbrd': {'dirdb': '', 'tsvname': ''},
              'mycobacterium_amrdetection': {'dirdb': '', 'tsvname': ''}
              }
isolatedb = 'bigsdb_mycobacterium_isolates'
seqdefdb ='bigsdb_mycobacterium_seqdef'

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--tsvfilepath', required=True, type=Path)
argument_parser.add_argument('--isolatename', required=True, type=str)
args = argument_parser.parse_args()
tsvfilepath = Path(args.tsvfilepath)
isolate_name = args.isolatename


# todo get sample/isolate name
# todo change curator/sender to NRC (all the 1s in inserts and updates)

outputtsvdict = {}
handle = open(tsvfilepath, 'r').readlines()
for line in handle:
    outputtsvdict[line.split('\t')[0]] = line.split('\t')[1].strip('\n')
# open db connection
# since we mostly only need one db, it can stay open during the entire script
con = psycopg2.connect(database=f"{isolatedb}", user='apache', password='remote',
                       host='127.0.0.1', port='')
con.autocommit = True
cur = con.cursor()

#main
def insert_typing_results():
    con = psycopg2.connect(database=f"{isolatedb}", user='apache', password='remote',
                           host='127.0.0.1', port='')
    con.autocommit = True
    cur = con.cursor()
    reportlink =f'<p><a href="/galaxyreports/mycobacterium/{isolate_name}/report.html"> html report</a></p>'
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'html', '{reportlink}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'tsv', '{reportlink.replace('html', 'tsv')}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'gyrB_group', '{outputtsvdict['51SNP-gyrB_group']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'Genetic_group', '{outputtsvdict['51SNP-genetic_group']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'SCG', '{outputtsvdict['51SNP-scg']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'snpit_species', '{outputtsvdict['snpit_species']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'snpit_lineage', '{outputtsvdict['snpit_lineage']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'snpit_sublineage', '{outputtsvdict['snpit_sublineage']}') ")
    dirlist = [] #dirlist serves to not insert duplicates (creates error in sql), for Listeria e.g. prs and prfA are included in two schemes
    for scheme in schemedict:
        if schemedict[scheme]['dirdb'] != '':
            dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
            for dir in dirs:
                if not dir.startswith('.') and dir not in dirlist:
                    dirlist.append(dir)
                    result = outputtsvdict['-'.join([schemedict[scheme]['tsvname'],dir])].split(',')
                    if result[2] == '100.00' and result[3] != '-' and eval(result[3]) == 1.0:
                        allele_id = int(result[1])
                        cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                    f"allele_id, status, method, sender, "
                                    f"curator, date_entered, datestamp) "
                                    f"VALUES('{dir}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                                    f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                    f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                    else:
                        continue
        elif schemedict[scheme]['dirdb'] == '':
            if schemedict[scheme]['tsvname'] == 'spoligotype_binary':
                x = 1
                for allele_id in list(outputtsvdict['spoligotype_binary']):
                    locus = ''.join(['Spacer', str(x).zfill(2)])
                    x += 1
                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                f"allele_id, status, method, sender, "
                                f"curator, date_entered, datestamp) "
                                f"VALUES('{locus}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                                f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                cur.execute(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                            f"'spoligotype_binary', '{outputtsvdict['spoligotype_binary']}') ")
                cur.execute(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                            f"'spoligotype_octal', '{outputtsvdict['spoligotype_octal']}') ")
            # elif schemedict[scheme]['tsvname'] == '51SNP':
                ## removed because unneccesary according to meeting
                # x = 1
                # while x < 52:
                #     locustsv = ''.join(['51SNP-SNP', str(x).zfill(2)])
                #     allele_sequence = outputtsvdict[locustsv].strip('*')
                #     locus = locustsv.replace('-', '_')
                #     if allele_sequence != '-':
                #         con2 = psycopg2.connect(database=f"{seqdefdb}", user='apache', password='remote',
                #                                host='127.0.0.1', port='')
                #         cur2 = con2.cursor()
                #         cur2.execute(f"SELECT allele_id FROM sequences WHERE sequence = '{allele_sequence}' AND locus = '{locus}'")
                #         allele_id = cur2.fetchall()[0][0]
                #         if allele_id != '2':
                #             sys.exit(f"This allele ({locus}: {allele_sequence}) was not found in the alleles in the seqdef database")
                #         con2.close()
                #         cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                #                     f"allele_id, status, method, sender, "
                #                     f"curator, date_entered, datestamp) "
                #                     f"VALUES('{locus}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                #                     f"'{allele_id}', 'confirmed', 'automatic', 1, "
                #                     f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                #     elif allele_sequence == '-':
                #         allele_id = 1
                #         cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                #                     f"allele_id, status, method, sender, "
                #                     f"curator, date_entered, datestamp) "
                #                     f"VALUES('{locus}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                #                     f"'{allele_id}', 'confirmed', 'automatic', 1, "
                #                     f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                #     x += 1
            elif scheme == 'mycobacterium_csbrd':
                for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                    locus = record.rstrip('_detected') # need to be careful with rstrip and strip but in this case no issue
                    if outputtsvdict[record] == 'False':
                        allele_id = 0
                    elif outputtsvdict[record] == 'True':
                        allele_id = 1
                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                f"allele_id, status, method, sender, "
                                f"curator, date_entered, datestamp) "
                                f"VALUES('{locus}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                                f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            elif scheme == 'mycobacterium_amrdetection':
                print('amr_detection')
                # make a dict with field and tsv names to be able to insert
                cur.execute(f"SELECT field FROM eav_fields WHERE category='AMR detection'")
                fields = cur.fetchall()
                print(fields)
                amr_metadata_fields_tsv = {}
                for field in fields:
                    if field[0].startswith('amr'):
                        amr_metadata_fields_tsv[field[0]] = field[0]
                    else:
                        amr_metadata_fields_tsv[field[0]] = ''.join(['amr_pheno_',field[0].split('_')[-1]])
                for bigsdbname, tsvname in amr_metadata_fields_tsv.items():
                    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                f"field, value)"
                                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                                f"'{bigsdbname}', '{outputtsvdict[tsvname]}') ")
                # AMR results
                cur.execute(f"SELECT locus FROM scheme_members WHERE scheme_id = (SELECT id FROM schemes WHERE name = 'AMR_detection_WHO')")
                loci = cur.fetchall()
                for locus in loci:
                    tsvname = '_'.join(['amr_mutations', str(locus[0]).replace('_int', '_(int.)')])
                    print(outputtsvdict[tsvname])
                    if outputtsvdict[tsvname] != '-':
                        for variant in outputtsvdict[tsvname].split(', '):
                            con2 = psycopg2.connect(database=f"{seqdefdb}", user='apache', password='remote',
                                                    host='127.0.0.1', port='')
                            cur2 = con2.cursor()
                            lastpartoflikequery = re.sub(r"([0-9]+(\.[0-9]+)?)",r"_\1_", variant.split('_')[-1].replace('(', '').replace(')', ''))
                            likequery = ''.join([variant.split('_')[-2],'%',lastpartoflikequery.replace('-_', '_-')])
                            likequeryabsolute = likequery.replace('-','')
                            # Bert explained that if the change is found in promotor, then it can change signs
                            # And also honestly the db is really discrepant, e.g. how likely is this:
                            # Rv1979c AA G_107_A Rv1979c_AA_G_107_A Uncertain significance CFZ CFZ_Uncertain_significance
                            # Rv1979c PROM g_-107_a Rv1979c_PROM_g_-107_a Uncertain significance CFZ CFZ_Uncertain_significance
                            # + there are really just duplicates in the db so I limit to 1, then its always the same.
                            cur2.execute(f"SELECT allele_id FROM sequences WHERE (allele_id LIKE '{likequery}' OR allele_id LIKE '{likequeryabsolute}') AND locus = '{locus[0]}' LIMIT 1")
                            present = cur2.fetchall()

                            #Sometimes not only the sign changes when its in a promotor, but also the location, easiest solution is just to insert.. Because sequences need to be unique for a locus, I take the longest sequence and add TAG
                            if likequery != likequeryabsolute and present == []:
                                cur2.execute(f"SELECT sequence FROM sequences WHERE locus = '{locus[0]}' ORDER BY sequence DESC LIMIT 1")
                                dummysequence = ''.join([cur2.fetchall()[0][0], 'TAG'])
                                cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                               VALUES('{locus[0]}','{likequery.replace('%','_PROM_')}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur2.execute(f"SELECT allele_id FROM sequences WHERE (allele_id LIKE '{likequery}' OR allele_id LIKE '{likequeryabsolute}') AND locus = '{locus[0]}' LIMIT 1")
                                present = cur2.fetchall()
                            allele_id = present[0][0]
                            print(allele_id)
                            con2.close()
                            # todo this is wrong : to test
                            # ETHAssociated_with_R_int  prom_inhA_g(-154)a should be
                            # ETH_Associated_with_R_int	inhA_PROM_g_-154_a
                            cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                        f"allele_id, status, method, sender, "
                                        f"curator, date_entered, datestamp) "
                                        f"VALUES('{locus[0]}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                                        f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")


    cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                f"VALUES((SELECT id FROM isolates WHERE isolate = '{isolate_name}'),(SELECT NOW()::TIMESTAMP), 'Typing results inserted', 1)")

# check whether sample exists
cur.execute(f"SELECT COUNT(*) FROM isolates WHERE isolate='{isolate_name}'")
sample_presence = cur.fetchall()
if sample_presence[0][0] == 0:
    # sample does not exist yet, but check first if any sample exists
    cur.execute(f"INSERT INTO isolates(id, "
                f"isolate, sender, curator, date_entered, datestamp)"
                f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM isolates)+1) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), "
                f"'{isolate_name}', 1, 1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
    cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                f"VALUES((SELECT id FROM isolates WHERE isolate = '{isolate_name}'),(SELECT NOW()::TIMESTAMP), 'Isolate record added', 1)")
    insert_typing_results()

elif sample_presence[0][0] == 1:
    # sample exists: check whether typing results or not (we do not bother checking for all schemes separately
    cur.execute(f"SELECT COUNT(*) FROM allele_designations WHERE isolate_id = (SELECT id FROM isolates WHERE isolate='{isolate_name}')")
    alleles_presence = cur.fetchall()
    if alleles_presence[0][0] == 0:
        # no allele designations are present so we insert them
        insert_typing_results()
    elif sample_presence[0][0] >= 1:
        sys.exit("This sample already contains typing results")

elif sample_presence[0][0] >= 1:
    # multiple samples with same isolate name are present, that means that there are multiple versions of the same sample
    # check newest version
    cur.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                f"isolate_id = (SELECT id FROM isolates WHERE isolate='{isolate_name}') ORDER BY date_entered DESC LIMIT 1")
    alleles_presence = cur.fetchall()
    if alleles_presence[0][0] == 0:
        # no allele designations are present so we insert them
        insert_typing_results()
    elif sample_presence[0][0] >= 1:
        sys.exit("This sample already contains typing results")



# close db connection
con.close()
