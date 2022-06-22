import os
import sys
import psycopg2
import argparse
from pathlib import Path
import re
import json
import smtplib
from email.message import EmailMessage
import socket

#leave dirdb empty for atypic typing schemes
schemedict = {'mycobacterium_mlst': {'dirdb': '/db/sequence_typing/mycobacterium/mlst', 'tsvname': 'mlst'},
              'mycobacterium_cgmlst': {'dirdb': '/db/sequence_typing/mycobacterium/cgmlst', 'tsvname': 'cgmlst'},
              'mycobacterium_spoligotyping': {'dirdb': '', 'tsvname': 'spoligotype_binary'},
              'mycobacterium_51SNPassay': {'dirdb': '', 'tsvname': '51SNP'},
              'mycobacterium_csbrd': {'dirdb': '', 'tsvname': ''},
              'mycobacterium_amrdetection': {'dirdb': '', 'tsvname': ''},
              'mycobacterium_hsp65': {'dirdb': '', 'tsvname': 'hits_hsp65'},
              'mycobacterium_pointfinder': {'dirdb': '', 'tsvname': 'pointfinder_mutations', 'schemename_html': 'PointFinder'},
              'mycobacterium_ncbi16s': {'dirdb': '', 'tsvname': 'hits_ncbi_16s'}
              }

emaildict = {"from": "bioit-dev1@wiv-isp.be",
    "to": "michael.kelchtermans@sciensano.be, benoit.bergkpinto@sciensano.be",
    "host": "smtp.wiv-isp.be"}

isolatedb = 'bigsdb_mycobacterium_isolates'
seqdefdb ='bigsdb_mycobacterium_seqdef'

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--tsvfilepath', required=True, type=Path)
argument_parser.add_argument('--isolatename', required=True, type=str)
argument_parser.add_argument('--uploadermailadress', required=True, type=str)
args = argument_parser.parse_args()
tsvfilepath = Path(args.tsvfilepath)
isolate_name = args.isolatename
uploadermailadress=args.uploadermailadress


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
    reportlink =f'<p><a href="/galaxyreports/mycobacterium/{isolate_name}/report.html" target="_blank"> html report</a></p>'
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                f"'html', '{reportlink}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                f"'tsv', '{reportlink.replace('html', 'tsv')}') ")
    if '51SNP-gyrB_group' in outputtsvdict:
        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                    f"field, value)"
                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                    f"'gyrB_group', '{outputtsvdict['51SNP-gyrB_group']}') ")
        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                    f"field, value)"
                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                    f"'Genetic_group', '{outputtsvdict['51SNP-genetic_group']}') ")
        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                    f"field, value)"
                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                    f"'SCG', '{outputtsvdict['51SNP-scg']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                f"'snpit_species', '{outputtsvdict['snpit_species']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                f"'snpit_lineage', '{outputtsvdict['snpit_lineage']}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
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
                                    f"VALUES('{dir}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                    f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                    f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                    else:
                        continue
        elif schemedict[scheme]['dirdb'] == '':
            if schemedict[scheme]['tsvname'] == 'spoligotype_binary' and schemedict[scheme]['tsvname'] in outputtsvdict:
                x = 1
                for allele_id in list(outputtsvdict[schemedict[scheme]['tsvname']]):
                    locus = ''.join(['Spacer', str(x).zfill(2)])
                    x += 1
                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                f"allele_id, status, method, sender, "
                                f"curator, date_entered, datestamp) "
                                f"VALUES('{locus}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                cur.execute(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                            f"'spoligotype_binary', '{outputtsvdict['spoligotype_binary']}') ")
                cur.execute(f"INSERT INTO eav_text(isolate_id, "
                            f"field, value)"
                            f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
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
                #                     f"VALUES('{locus}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                #                     f"'{allele_id}', 'confirmed', 'automatic', 1, "
                #                     f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                #     elif allele_sequence == '-':
                #         allele_id = 1
                #         cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                #                     f"allele_id, status, method, sender, "
                #                     f"curator, date_entered, datestamp) "
                #                     f"VALUES('{locus}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                #                     f"'{allele_id}', 'confirmed', 'automatic', 1, "
                #                     f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                #     x += 1
            elif scheme == 'mycobacterium_csbrd' and 'csb_detected' in outputtsvdict:
                for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                    locus = record.rstrip('_detected') # need to be careful with rstrip and strip but in this case no issue
                    if outputtsvdict[record] == 'False':
                        allele_id = 0
                    elif outputtsvdict[record] == 'True':
                        allele_id = 1
                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                f"allele_id, status, method, sender, "
                                f"curator, date_entered, datestamp) "
                                f"VALUES('{locus}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            elif scheme == 'mycobacterium_amrdetection':
                # make a dict with field and tsv names to be able to insert
                cur.execute(f"SELECT field FROM eav_fields WHERE category='AMR detection'")
                fields = cur.fetchall()
                amr_metadata_fields_tsv = {}
                for field in fields:
                    if field[0].startswith('amr'):
                        amr_metadata_fields_tsv[field[0]] = field[0]
                    else:
                        amr_metadata_fields_tsv[field[0]] = ''.join(['amr_pheno_',field[0].split('_')[-1]])
                for bigsdbname, tsvname in amr_metadata_fields_tsv.items():
                    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                f"field, value)"
                                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
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
                            con2.autocommit = True
                            cur2 = con2.cursor()
                            variantreformatted = variant.replace('(', '').replace(')', '')
                            # Bert explained that if the change is found in promotor, then it can change signs
                            # And also honestly the db is really discrepant, e.g. how likely is this:
                            # Rv1979c AA G_107_A Rv1979c_AA_G_107_A Uncertain significance CFZ CFZ_Uncertain_significance
                            # Rv1979c PROM g_-107_a Rv1979c_PROM_g_-107_a Uncertain significance CFZ CFZ_Uncertain_significance
                            # + there are really just duplicates in the db so I limit to 1, then its always the same.
                            cur2.execute(f"SELECT allele_id FROM sequences WHERE allele_id = '{variantreformatted}' AND locus = '{locus[0]}' LIMIT 1")
                            present = cur2.fetchall()
                            #Sometimes not only the sign changes when its in a promotor, but also the location, easiest solution is just to insert after it is found. Because sequences need to be unique for a locus, I take the longest sequence and add TAG
                            if present == []:
                                cur2.execute(f"SELECT sequence FROM sequences WHERE locus = '{locus[0]}' ORDER BY sequence DESC LIMIT 1")
                                possiblelongestdummypresent = cur2.fetchall()
                                if possiblelongestdummypresent == []:
                                    dummysequence = 'TAG'
                                else:
                                    dummysequence = ''.join([possiblelongestdummypresent[0][0], 'TAG'])
                                cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                               VALUES('{locus[0]}','{variantreformatted}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur2.execute(f"SELECT allele_id FROM sequences WHERE allele_id LIKE '{variantreformatted}' AND locus = '{locus[0]}' LIMIT 1")
                                present = cur2.fetchall()
                            allele_id = present[0][0]
                            print(allele_id)
                            con2.close()
                            cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                        f"allele_id, status, method, sender, "
                                        f"curator, date_entered, datestamp) "
                                        f"VALUES('{locus[0]}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                        f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            elif scheme == 'mycobacterium_hsp65':
                listofhits = outputtsvdict[schemedict[scheme]['tsvname']]
                # this might look something like this currently: [["Cluster_0", "seq_132", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. tuberculosis", "ATCC 27294, H37Rv(T)"], ["Cluster_0", "seq_19", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. bovis", "CIP 105234(T)"], ["Cluster_0", "seq_23", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. caprae", "CIP 105776(T)"], ["Cluster_0", "seq_81", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. microti", "CIP 104256, ATCC 19422(T)"]]

                if listofhits != '[]':
                    y = 0
                    while y <= (len((json.loads(listofhits))) - 1):
                        hit = '_'.join(['hsp65', (json.loads(listofhits))[y][-2].strip('"').replace(' ', '_').replace('.', '')])
                        print(hit)
                        cur.execute(f"INSERT INTO eav_boolean(isolate_id, "
                                    f"field, value)"
                                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                                    f"'{hit}', 't') ")
                        y+=1

            elif scheme == 'mycobacterium_pointfinder':
                # for pointfinder, only hits that infer resistance are of importance, other hits dont give any information.
                listofhits = outputtsvdict[schemedict[scheme]['tsvname']]
                # this might look like this: [["drrA p.H309D", "CAC -> GAC", "H -> D", "Unknown", "-"], ["embA p.P958Q", "CCG -> CAG", "P -> Q", "Unknown", "-"], ["embB p.N13S", "AAT -> AGT", "N -> S", "Unknown", "-"], ["embB p.E378A", "GAG -> GCG", "E -> A", "Unknown", "-"], ["embC p.T270I", "ACC -> ATC", "T -> I", "Unknown", "-"], ["gyrA p.E21Q", "GAG -> CAG", "E -> Q", "Unknown", "-"], ["gyrA p.S95T", "AGC -> ACC", "S -> T", "Unknown", "-"], ["gyrA p.D639A", "GAC -> GCC", "D -> A", "Unknown", "-"], ["gyrA p.G668D", "GGC -> GAC", "G -> D", "Unknown", "-"], ["gyrB p.A403S", "GCG -> TCG", "A -> S", "Unknown", "-"], ["iniA p.N88S", "AAT -> AGT", "N -> S", "Unknown", "-"], ["iniA p.H481Q", "CAT -> CAG", "H -> Q", "Unknown", "-"], ["katG p.R463L", "CGG -> CTG", "R -> L", "Unknown", "-"], ["nuoA n.-95T>G", "T -> G", "Promoter mutations", "Unknown", "-"], ["pncA p.H57D", "CAC -> GAC", "H -> D", "PYRAZINAMIDE", "19209951"], ["rpsA p.A440T", "GCG -> ACG", "A -> T", "Unknown", "-"], ["ubiA p.E149D", "GAA -> GAC", "E -> D", "Unknown", "-"]]
                if listofhits != '[]':
                    eavhtmltable = '<table class="data"><tr><th>Hit</th><th>Antibiotic</th></tr>'
                    y = 0
                    con2 = psycopg2.connect(database=f"{seqdefdb}", user='apache', password='remote',
                                            host='127.0.0.1', port='')
                    cur2 = con2.cursor()
                    con2.autocommit = True
                    while y <= (len((json.loads(listofhits))) - 1):
                        hit = (json.loads(listofhits))[y]
                        if hit[-2] != "Unknown":
                            # Seeing as the allele db of pointfinder is empty at the beginning because the db is too hard to understand, we gradually add alleles.
                            # sometimes a mutation will give resistance to more than 1 AB
                            antibiotics = hit[-2].split(',')
                            for antibiotic in antibiotics:
                                antibiotic_reformatted = '_'.join(['POINTFINDER', antibiotic.replace('-', '_').replace(' ', '_').upper()])
                                print(antibiotic)
                                print(antibiotic_reformatted)
                                mutation = hit[0].replace('.', '_').replace(' ', '_')
                                eavhtmltable = eavhtmltable + ''.join(
                                    ['<tr><td><a href="/galaxyreports/mycobacterium/', isolate_name, '/report.html#',
                                     schemedict[scheme]['schemename_html'], '" target="_blank">',
                                     hit[0], '</a></td>'])
                                eavhtmltable = eavhtmltable + ''.join(['<td>', antibiotic, '</td></tr>'])
                                cur2.execute(f"SELECT allele_id FROM sequences WHERE allele_id = '{mutation}' and locus = '{antibiotic_reformatted}'")
                                present = cur2.fetchall()
                                if present == []:
                                    cur2.execute(f"SELECT sequence FROM sequences WHERE locus  ='{antibiotic_reformatted}' ORDER BY CHAR_LENGTH(sequence) DESCLIMIT 1")
                                    longest_dummy_sequence = cur2.fetchall()
                                    if longest_dummy_sequence == []:
                                        dummysequence = 'TAG'
                                    else:
                                        dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                    cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                   VALUES('{antibiotic_reformatted}','{mutation}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{antibiotic_reformatted}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                            f"'{mutation}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        y += 1
                    eavhtmltable = eavhtmltable + '</table>'
                    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                                f"field, value)"
                                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                                f"'pointfinder_hits', '{eavhtmltable}') ")
                    con2.close()
            elif scheme == 'mycobacterium_ncbi16s':
                # ncbi 16s contains duplicate species
                listofhits = outputtsvdict[schemedict[scheme]['tsvname']]
                # this might look like this: [["Cluster_24", "NR_044826.2", "100.00", "1532/1532", "NODE_59_length_20721_cov_23.830436", "2360..3891", "Mycobacterium tuberculosis strain H37Rv 16S ribosomal RNA, complete sequence", "NR_044826.2"], ["Cluster_24", "NR_102810.2", "100.00", "1532/1532", "NODE_59_length_20721_cov_23.830436", "2360..3891", "Mycobacterium tuberculosis strain H37Rv 16S ribosomal RNA, complete sequence", "NR_102810.2"]]
                speciesandstrainhits = []
                if listofhits != '[]':
                    for hit in json.loads(listofhits):
                        speciesname = '_'.join([hit[-2].split(' ')[0], hit[-2].split(' ')[1]])
                        print(speciesname)
                        if speciesname not in speciesandstrainhits:
                            speciesandstrainhits.append(speciesname)
                        strainname = '_'.join([hit[-2].split(' ')[0], hit[-2].split(' ')[1], hit[-2].split(' ')[2], hit[-2].split(' ')[3]])
                        print(strainname)
                        if strainname not in speciesandstrainhits:
                            speciesandstrainhits.append(strainname)
                print(speciesandstrainhits)
                for hit in speciesandstrainhits:
                    hit_formatted = '_'.join(['ncbi16s', hit])
                    # check whether already exists in eav
                    cur.execute(f"SELECT count(*) FROM eav_fields WHERE category='NCBI 16S' AND field = '{hit_formatted}'")
                    eav_exists = cur.fetchall()
                    if eav_exists[0][0] == 0:
                        cur.execute(f"INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) VALUES('{hit_formatted}', 'boolean', 'NCBI 16S', '', 't', 't', (SELECT CURRENT_DATE), 1)")
                    cur.execute(f"INSERT INTO eav_boolean(isolate_id, "
                                f"field, value)"
                                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                                f"'{hit_formatted}', 't') ")

    cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate = '{isolate_name}'),(SELECT NOW()::TIMESTAMP), 'Typing results inserted', 1)")

def send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)

# check whether sample exists
cur.execute(f"SELECT COUNT(*) FROM isolates WHERE isolate='{isolate_name}'")
sample_presence = cur.fetchall()
if sample_presence[0][0] == 0:
    # sample does not exist yet, but check first if any sample exists
    cur.execute(f"INSERT INTO isolates(id, "
                f"isolate, sender, curator, date_entered, datestamp, uploader)"
                f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM isolates)+1) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), "
                f"'{isolate_name}', 1, 1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), '{uploadermailadress}')")
    cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate = '{isolate_name}'),(SELECT NOW()::TIMESTAMP), 'Isolate record added', 1)")
    try:
        insert_typing_results()
    except Exception as exceptionmessage:
        send_email(
            f'Error inserting output of mycobacterium pipeline to bigsdb for sample {isolate_name} on host {socket.gethostname()}',
            f"{exceptionmessage}", emaildict)

elif sample_presence[0][0] == 1:
    # sample exists: check whether typing results or not (we do not bother checking for all schemes separately
    cur.execute(f"SELECT COUNT(*) FROM allele_designations WHERE isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}')")
    alleles_presence = cur.fetchall()
    if alleles_presence[0][0] == 0:
        # no allele designations are present so we insert them
        try:
            insert_typing_results()
        except Exception as exceptionmessage:
            send_email(
                f'Error inserting output of mycobacterium pipeline to bigsdb for sample {isolate_name} on host {socket.gethostname()}',
                f"{exceptionmessage}", emaildict)
    elif sample_presence[0][0] >= 1:
        sys.exit("This sample already contains typing results")

elif sample_presence[0][0] >= 1:
    # multiple samples with same isolate name are present, that means that there are multiple versions of the same sample
    # check newest version
    cur.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                f"isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}')")
    alleles_presence = cur.fetchall()
    if alleles_presence[0][0] == 0:
        # no allele designations are present so we insert them
        try:
            insert_typing_results()
        except Exception as exceptionmessage:
            send_email(
                f'Error inserting output of mycobacterium pipeline to bigsdb for sample {isolate_name} on host {socket.gethostname()}',
                f"{exceptionmessage}", emaildict)
    elif sample_presence[0][0] >= 1:
        sys.exit("This sample already contains typing results")

# close db connection
con.close()
