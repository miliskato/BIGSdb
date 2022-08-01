import os
import sys
import psycopg2
import argparse
from pathlib import Path
import json
import re
import ast
import smtplib
from email.message import EmailMessage
import socket
import traceback

schemedict = {'salmonella_mlst': {'dirdb': '/db/sequence_typing/salmonella/mlst', 'tsvname': 'mlst'},
              'salmonella_cgmlst': {'dirdb': '/db/sequence_typing/salmonella/cgmlst', 'tsvname': 'cgmlst'},
              'salmonella_pointfinder': {'dirdb': '', 'tsvname': 'pointfinder_mutations', 'schemename_html': 'PointFinder'},
              'salmonella_genotyphi': {'dirdb': '', 'tsvname': 'genotyphi'},
              'salmonella_serotyping': {'dirdb': '', 'tsvname': 'serotyping'},
              'salmonella_spifinder': {'dirdb': '', 'tsvname': 'spifinder'}
              }
genedetectiondict = {'salmonella_ndaro':
                         {'clusteredfasta': '/db/gene_detection/NCBI_AMR/ncbi_amr-clustered_80.fasta',
                          'metadatafile': '/db/gene_detection/NCBI_AMR/mapping_full.json',
                          'tsvname': 'hits_ncbi_amr',
                          'schemename_bigsdb': 'NCBI_AMR',
                          'schemename_html': 'NCBI AMR genes'},
                     'salmonella_resfinder': {
                         'clusteredfasta': '/db/gene_detection/ResFinder/resfinder-clustered_80.fasta',
                         'metadatafile': '/db/gene_detection/ResFinder/mapping_full.json',
                         'tsvname': 'hits_resfinder',
                         'schemename_bigsdb': 'ResFinder',
                         'schemename_html': 'ResFinder'},
                     'salmonella_vfdbcore': {
                         'clusteredfasta': '/db/gene_detection/VFDB_core/vfdb_core-clustered_80.fasta',
                         'metadatafile': '/db/gene_detection/VFDB_core/mapping_full.json',
                         'tsvname': 'hits_vfdb_core',
                         'schemename_bigsdb': 'VFDB_core',
                         'schemename_html': 'Virulence Factor DB - Core'},
                     'salmonella_plasmidfinder': {
                         'clusteredfasta': '/db/gene_detection/PlasmidFinder-entero/plasmidfinder-entero-clustered_80.fasta',
                         'metadatafile': '/db/gene_detection/PlasmidFinder-entero/mapping_full.json',
                         'tsvname': 'hits_plasmidfinder',
                         'schemename_bigsdb': 'PlasmidFinder_entero',
                         'schemename_html': 'PlasmidFinder - Enterobacteriaceae'}
                     }

emaildict = {"from": "bioit-dev1@wiv-isp.be",
    "to": "michael.kelchtermans@sciensano.be, benoit.bergkpinto@sciensano.be",
    "host": "smtp.wiv-isp.be"}

isolatedb = 'bigsdb_salmonella_isolates'
seqdefdb = 'bigsdb_salmonella_seqdef'
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
# since we only need one db, it can stay open during the entire script
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
    con2 = psycopg2.connect(database=f"{seqdefdb}", user='apache', password='remote',
                            host='127.0.0.1', port='')
    cur2 = con2.cursor()
    con2.autocommit = True
    reportlink =f'<p><a href="/galaxyreports/salmonella/{isolate_name}/report.html" target="_blank"> html report</a></p>'
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                f"'html', '{reportlink}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                f"'tsv', '{reportlink.replace('html', 'tsv')}') ")
    dirlist = [] #dirlist serves to not insert duplicates (creates error in sql), for salmonella e.g. prs and prfA are included in two schemes
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
            if scheme == 'salmonella_pointfinder':
                # for pointfinder, only hits that infer resistance are of importance, other hits dont give any information.
                listofhits = outputtsvdict[schemedict[scheme]['tsvname']]
                # this might look like this: [["drrA p.H309D", "CAC -> GAC", "H -> D", "Unknown", "-"], ["embA p.P958Q", "CCG -> CAG", "P -> Q", "Unknown", "-"], ["embB p.N13S", "AAT -> AGT", "N -> S", "Unknown", "-"], ["embB p.E378A", "GAG -> GCG", "E -> A", "Unknown", "-"], ["embC p.T270I", "ACC -> ATC", "T -> I", "Unknown", "-"], ["gyrA p.E21Q", "GAG -> CAG", "E -> Q", "Unknown", "-"], ["gyrA p.S95T", "AGC -> ACC", "S -> T", "Unknown", "-"], ["gyrA p.D639A", "GAC -> GCC", "D -> A", "Unknown", "-"], ["gyrA p.G668D", "GGC -> GAC", "G -> D", "Unknown", "-"], ["gyrB p.A403S", "GCG -> TCG", "A -> S", "Unknown", "-"], ["iniA p.N88S", "AAT -> AGT", "N -> S", "Unknown", "-"], ["iniA p.H481Q", "CAT -> CAG", "H -> Q", "Unknown", "-"], ["katG p.R463L", "CGG -> CTG", "R -> L", "Unknown", "-"], ["nuoA n.-95T>G", "T -> G", "Promoter mutations", "Unknown", "-"], ["pncA p.H57D", "CAC -> GAC", "H -> D", "PYRAZINAMIDE", "19209951"], ["rpsA p.A440T", "GCG -> ACG", "A -> T", "Unknown", "-"], ["ubiA p.E149D", "GAA -> GAC", "E -> D", "Unknown", "-"]]
                if listofhits != '[]':
                    eavhtmltable = '<table class="data"><tr><th>Hit</th><th>Antibiotic</th></tr>'
                    y = 0
                    while y <= (len((json.loads(listofhits))) - 1):
                        hit = (json.loads(listofhits))[y]
                        if hit[3] != "Unknown":
                            # Seeing as the allele db of pointfinder is empty at the beginning because the db is too hard to understand, we gradually add alleles.
                            # sometimes a mutation will give resistance to more than 1 AB
                            antibiotics = hit[3].split(',')
                            for antibiotic in antibiotics:
                                antibiotic_reformatted = '_'.join(['POINTFINDER', antibiotic.replace('-', '_').replace(' ', '_').upper()])
                                mutation = hit[0].replace('.', '_').replace(' ', '_')
                                eavhtmltable = eavhtmltable + ''.join(
                                    ['<tr><td><a href="/galaxyreports/salmonella/', isolate_name, '/report.html#',
                                     schemedict[scheme]['schemename_html'], '" target="_blank">',
                                     hit[0], '</a></td>'])
                                eavhtmltable = eavhtmltable + ''.join(['<td>', antibiotic, '</td></tr>'])
                                cur2.execute(f"SELECT allele_id FROM sequences WHERE allele_id = '{mutation}' and locus = '{antibiotic_reformatted}'")
                                present = cur2.fetchall()
                                if present == []:
                                    cur2.execute(f"SELECT sequence FROM sequences WHERE locus  ='{antibiotic_reformatted}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
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
            elif scheme == 'salmonella_genotyphi' and 'genotyphi_lineage' in outputtsvdict:
                cur.execute(f"SELECT field FROM eav_fields WHERE field like 'genotyphi%'")
                genotyphi_susc_list = cur.fetchall()
                for item in genotyphi_susc_list:
                    if item[0] in outputtsvdict:

                        susceptibility = outputtsvdict[item[0]]
                        cur.execute(
                            f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),'{item[0]}','{susceptibility}')")
                        # insert new alleles
                        variant = item[0].replace('susceptibility', 'variants')
                        gene = item[0].replace('susceptibility', 'genes')
                        genotyphi_field = item[0].replace('_susceptibility', '').upper()
                        # get the genes and variants
                        future_alleles = outputtsvdict[variant].split(';') + outputtsvdict[gene].split(';')
                        for i in range(0, len(future_alleles)):
                            if future_alleles[i] != '-':
                                cur2.execute(
                                    f"SELECT allele_id FROM sequences WHERE allele_id = '{future_alleles[i]}' and locus = '{genotyphi_field}'")
                                present_genotyphi = cur2.fetchall()
                                if present_genotyphi == []:
                                    cur2.execute(
                                        f"SELECT sequence FROM sequences WHERE locus  ='{genotyphi_field}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                    longest_dummy_sequence = cur2.fetchall()
                                    if longest_dummy_sequence == []:
                                        dummysequence = 'TAG'
                                    else:
                                        dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                    cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                         VALUES('{genotyphi_field}','{future_alleles[i]}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{genotyphi_field}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                            f"'{future_alleles[i]}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

            elif scheme == 'salmonella_serotyping':
                cur.execute(f"SELECT field FROM eav_fields WHERE category = 'Serotyping' ")
                serotyping_list = cur.fetchall()
                for sero in serotyping_list:
                    tool = re.sub('_[a-z]*$','', sero[0])
                    field_type = sero[0].split('_')[len(sero[0].split('_'))-1]
                    # class for serotyping formula processing.
                    class formula:
                        def __init__(self,rawFormula,tool,isolate_name):
                            self.antigens={ "O_antigen" : rawFormula.split(':')[0].split(','),
                                            "H1_antigen" : rawFormula.split(':')[1].split(','),
                                             "H2_antigen" : rawFormula.split(':')[2].split(',')}
                            self.tool = tool
                            self.isolate_name = isolate_name
                        def __check_if_exist_in_seqdef(self, field, entry):
                            cur2.execute(
                                f"SELECT allele_id FROM sequences WHERE allele_id = '{entry}' and locus = '{field}'")
                            return(cur2.fetchall())

                        def __generate_dummy_sequence(self, field):
                            cur2.execute(
                                f"SELECT sequence FROM sequences WHERE locus  ='{field}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                            longest_dummy_sequence = cur2.fetchall()
                            if longest_dummy_sequence == []:
                                dummysequence = 'TAG'
                            else:
                                dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                            return dummysequence

                        def insert_antigens_into_db(self):
                            antigens=["O_antigen","H1_antigen" ,"H2_antigen"]
                            for antigen in antigens:
                                field = (f'{self.tool}_{antigen}').upper()
                                entries = self.antigens[antigen]
                                for entry in entries:
                                    if entry != '-':
                                        presence = self.__check_if_exist_in_seqdef(field, entry)
                                        if presence == []:
                                            dummysequence = self.__generate_dummy_sequence(field)
                                            cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                                      VALUES('{field}','{entry}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                        cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                    f"allele_id, status, method, sender, "
                                                    f"curator, date_entered, datestamp) "
                                                    f"VALUES('{field}', (SELECT MAX(id) FROM isolates WHERE isolate='{self.isolate_name}'), "
                                                    f"'{entry}', 'confirmed', 'automatic', 1, "
                                                    f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                    if tool == 'sistr':
                        if field_type == 'formula':
                            if f'{tool}_serotype_antigenic_formula' in outputtsvdict:
                                serotypingInsert = outputtsvdict[f'{tool}_serotype_antigenic_formula']
                                if serotypingInsert != '-':
                                    sistr_formula = formula(serotypingInsert, tool, isolate_name)
                                    sistr_formula.insert_antigens_into_db()
                                    cur.execute(
                                    f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),'{sero[0]}','{serotypingInsert}')")
                        elif field_type == 'serotype':
                            if f'{tool}_serotype_concensus' in outputtsvdict:
                                serotypingInsert = outputtsvdict[f'{tool}_serotype_concensus']
                                if serotypingInsert != '-':
                                    cur.execute(
                                    f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),'{sero[0]}','{serotypingInsert}')")
                    else:
                        if field_type == 'formula' and f'{tool} Predicted antigenic profile:' in outputtsvdict:
                            serotypingInsert = outputtsvdict[f'{tool} Predicted antigenic profile:']
                            seqsero_formula = formula(serotypingInsert, tool, isolate_name)
                            seqsero_formula.insert_antigens_into_db()
                            if serotypingInsert != '-:-:-':
                                cur.execute(
                                f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),'{sero[0]}','{serotypingInsert}')")
                        elif field_type == 'serotype' and f'{tool} Predicted serotype:' in outputtsvdict:
                            serotypingInsert = outputtsvdict[f'{tool} Predicted serotype:']
                            if serotypingInsert != '- -:-:-':
                                cur.execute(
                                f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),'{sero[0]}','{serotypingInsert}')")

            elif scheme == 'salmonella_spifinder':
                schemes_spifinder=['spifinder_fastq','spifinder_fasta']
                for scheme in schemes_spifinder:
                    if 'spifinder_fastq' in outputtsvdict:
                        hits = outputtsvdict[scheme]
                        if hits != '[]':
                            hits = ast.literal_eval(hits)
                            for l in range(0, len(hits)):
                                spifinder_entry = f"CatFunc{hits[l]['category_function']}__{hits[l]['accession']}"
                                spifinder_field = (f"{scheme}_{hits[l]['SPI']}").upper()
                                cur2.execute(
                                    f"SELECT allele_id FROM sequences WHERE allele_id = '{spifinder_entry}' and locus = '{spifinder_field}'")
                                present_spifinder = cur2.fetchall()
                                if present_spifinder == []:
                                    cur2.execute(
                                        f"SELECT sequence FROM sequences WHERE locus  ='{spifinder_field}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                    longest_dummy_sequence = cur2.fetchall()
                                    if longest_dummy_sequence == []:
                                        dummysequence = 'TAG'
                                    else:
                                        dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                    cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                        VALUES('{spifinder_field}','{spifinder_entry}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur.execute(f"SELECT FROM allele_designations WHERE locus = '{spifinder_field}' AND "
                                            f" isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}')"
                                            f" AND allele_id = '{spifinder_entry}'")
                                presence_allele_designation = cur.fetchall()
                                if presence_allele_designation == []:
                                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{spifinder_field}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                            f"'{spifinder_entry}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")


                con2.close() #close seqdef database

    cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate = '{isolate_name}'),(SELECT NOW()::TIMESTAMP), 'Typing results inserted', 1)")

    for scheme in genedetectiondict:
        # first create a cluster content list
        sequencefile = json.load(open(Path(genedetectiondict[scheme]['metadatafile']), 'r'))
        sequencenamedict = {}
        ncbi_ab_class_dict = {}
        for x in list(sequencefile):
            # sequencename becomes accession concatenated with allele because in e.g. Resfinder, multiple accessions are not unique.
            # sequencefile looks like this: {'seq_0': {'accession': 'NG_047553.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047553.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_1': {'accession': 'NG_047554.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047554.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_2': {'accession': 'NG_056058.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_056058.1_BcII', 'cluster': 'Cluster_561'}, 'seq_3': {'accession': 'NG_047221.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_047221.1_BcII', 'cluster': 'Cluster_561'}}
            # in VFDB, there are accessions with name "null", this breaks the script, therefore an empty space is added, and the allele should be enough to find.
            if sequencefile[x]['accession'] is None:
                sequencefile[x]['accession'] = "-"
            sequencenamedict[x] = '_'.join(
                [(sequencefile[x]['accession']), (sequencefile[x]['allele']).replace("'", "")])
            if genedetectiondict[scheme]['schemename_bigsdb'] == 'NCBI_AMR':
                ncbi_ab_class_dict['_'.join(
                    [(sequencefile[x]['accession']), (sequencefile[x]['allele']).replace("'", "")])] = '_'.join(
                    ['NCBI_AMR', sequencefile[x]['class'].upper().replace(' ', '_')])

        clusterfile = open(Path(genedetectiondict[scheme]['clusteredfasta']), 'r').readlines()
        clusterdict = {}
        for line in clusterfile:
            # line looks like this: >0__Cluster_0__seq_4648__seq_4648
            if line.startswith('>'):
                # key is sequencename from previous dict, value is cluster
                clusterdict[sequencenamedict[line.split('__')[2]]] = '_'.join(
                    [genedetectiondict[scheme]['schemename_bigsdb'], ''.join(['Gene', line.split('__')[1]])])
                # e.g. sequencenamedict['NG_047553.11567214_ble'] = 'NCBI_AMR_GeneCluster_0'

        con = psycopg2.connect(database=f"{isolatedb}", user="apache", password="remote",
                               host="127.0.0.1", port="")
        cur = con.cursor()
        con.autocommit = True
        listofhits = outputtsvdict[genedetectiondict[scheme]['tsvname']].replace("'", "")
        # this might look something like this currently: [["Cluster_15", "ActA_1", "94.20", "1915/1920", "NODE_24_length_29899_cov_7.347474", "26015..27929", "NC_003210.1"], ["Cluster_59", "AgrA_1", "98.90", "729/729", "NODE_2_length_347775_cov_7.239843", "324619..325347", "NC_003210.1"], ["Cluster_67", "clpp_1", "96.82", "597/597", "NODE_5_length_187626_cov_7.284412", "124253..124849", "NC_003210.1"], ["Cluster_55", "codY_1", "95.26", "780/780", "NODE_14_length_77047_cov_5.065224", "15699..16478", "NC_003210.1"], ["Cluster_28", "ctaP_1", "97.91", "1575/1575", "NODE_8_length_111969_cov_7.509254", "4180..5754", "NC_003210.1"], ["Cluster_72", "ctsR_1", "96.95", "459/459", "NODE_3_length_239115_cov_6.610227", "396..854", "NC_003210.1"], ["Cluster_40", "dal_1", "92.32", "1107/1107", "NODE_13_length_82610_cov_5.507547", "35258..36364", "NC_003210.1"], ["Cluster_61", "degU_1", "98.84", "687/687", "NODE_5_length_187626_cov_7.284412", "72335..73021", "NC_003210.1"], ["Cluster_29", "dltA_1", "96.02", "1533/1533", "NODE_18_length_59308_cov_5.458390", "50475..52007", "NC_003210.1"]]

        if listofhits != '[]':
            cur.execute(f"INSERT INTO eav_text_hidden(isolate_id, "
                        f"field, value)"
                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                        f"'{genedetectiondict[scheme]['schemename_bigsdb']}', '{listofhits}') ")

            eavhtmltable = '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
            clusterhitlist = []  # in case loci that were in different clusters at some point get in the same cluster
            y = 0
            # open seqdef for second part of AB schemes
            con2 = psycopg2.connect(database=f"{seqdefdb}", user="apache", password="remote",
                                    host="127.0.0.1", port="")
            cur2 = con2.cursor()
            con2.autocommit = True
            while y <= (len((json.loads(listofhits))) - 1):
                # allele is always position 1 and accession is always last position (-1)
                hit = '_'.join([(json.loads(listofhits))[y][-1], (json.loads(listofhits))[y][1]])
                clusterhit = clusterdict[hit]
                # append Cluster
                eavhtmltable = eavhtmltable + ''.join(
                    ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                # append Locus
                if scheme != 'salmonella_vfdbcore':
                    eavhtmltable = eavhtmltable + ''.join(
                        ['<td><a href="/galaxyreports/salmonella/', isolate_name, '/report.html#',
                         genedetectiondict[scheme]['schemename_html'], '" target="_blank">',
                         (json.loads(listofhits))[y][1], '</a></td></tr>'])
                else:
                    eavhtmltable = eavhtmltable + ''.join(
                        ['<td><a href="/galaxyreports/salmonella/', isolate_name, '/report.html#',
                         genedetectiondict[scheme]['schemename_html'], '" target="_blank">',
                         (json.loads(listofhits))[y][-2], '</a></td></tr>'])

                if clusterhit not in clusterhitlist:
                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                f"allele_id, status, method, sender, "
                                f"curator, date_entered, datestamp) "
                                f"VALUES('{clusterhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                f"1, 'confirmed', 'automatic', 1, "
                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                clusterhitlist.append(clusterhit)

                # Part 2 for the AB schemes
                if genedetectiondict[scheme]['schemename_bigsdb'] == 'NCBI_AMR':
                    ncbi_class = ncbi_ab_class_dict[hit]
                    # gene or allele is always position 1
                    genehit = (json.loads(listofhits))[y][1].replace('.', '_').replace(' ', '_')
                    # AB from hit is always position -2
                    ABhit_s = '_'.join(['NCBI_AMR', (json.loads(listofhits))[y][-2].upper().replace(' ', '_')])
                    cur2.execute(f"SELECT COUNT(*) FROM loci WHERE "
                                 f"id='{ncbi_class}'")
                    classpresent = cur2.fetchall()
                    # if locus exists (then it always exists in class because first, but not necesarily in subclass (=AB))
                    if classpresent[0][0] == 1:
                        cur2.execute(f"SELECT COUNT(*) FROM sequences WHERE "
                                     f"locus='{ncbi_class}' AND allele_id='{genehit}'")
                        allelepresent = cur2.fetchall()
                        if allelepresent[0][0] == 0:
                            cur2.execute(
                                f"SELECT sequence FROM sequences WHERE locus='{ncbi_class}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                            longest_dummy_sequence = cur2.fetchall()
                            if longest_dummy_sequence == []:
                                dummysequence = 'TAG'
                            else:
                                dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                            cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                   VALUES('{ncbi_class}','{genehit}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                        f"allele_id, status, method, sender, "
                                        f"curator, date_entered, datestamp) "
                                        f"VALUES('{ncbi_class}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                        f"'{genehit}', 'confirmed', 'automatic', 1, "
                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        elif allelepresent[0][0] == 1:
                            cur.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                                        f"locus='{ncbi_class}' AND allele_id='{genehit}' AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}')")
                            designationpresent = cur.fetchall()
                            if designationpresent[0][0] == 0:
                                cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{ncbi_class}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                            f"'{genehit}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                    # else not exists; add into
                    elif classpresent[0][0] == 0:
                        # seqdef db
                        cur2.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                              VALUES('{ncbi_class}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                        cur2.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                              VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB_CLASS'), '{ncbi_class}', 1, (SELECT CURRENT_DATE))")
                        cur2.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                              VALUES(1, '{ncbi_class}', 1, (SELECT CURRENT_DATE))")
                        cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                               VALUES('{ncbi_class}','{genehit}','TAG','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        # isolate db
                        dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f"{seqdefdb}",
                                            '&page=alleleInfo&locus=', f"{ncbi_class}", '&allele_id=[?]'])
                        cur.execute(
                            f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                            f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                            f"curator, date_entered, datestamp) \
                                              VALUES('{ncbi_class}','DNA','text', 't', 't', '{seqdefdb}', '{ncbi_class}', "
                            f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                            f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                        cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                              VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB_CLASS'), '{ncbi_class}', 1, (SELECT CURRENT_DATE))")
                        cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                    f"allele_id, status, method, sender, "
                                    f"curator, date_entered, datestamp) "
                                    f"VALUES('{ncbi_class}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                    f"'{genehit}', 'confirmed', 'automatic', 1, "
                                    f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                    for ABhit in ABhit_s.split('/'):
                        cur2.execute(f"SELECT COUNT(*) FROM loci WHERE "
                                     f"id='{ABhit}'")
                        ABpresent = cur2.fetchall()
                        # if locus exists (then it always exists in class because first, but not necesarily in subclass (=AB))
                        if ABpresent[0][0] == 1:
                            cur2.execute(f"SELECT COUNT(*) FROM sequences WHERE "
                                         f"locus='{ABhit}' AND allele_id='{genehit}'")
                            allelepresent = cur2.fetchall()
                            if allelepresent[0][0] == 0:
                                cur2.execute(
                                    f"SELECT sequence FROM sequences WHERE locus='{ABhit}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                longest_dummy_sequence = cur2.fetchall()
                                if longest_dummy_sequence == []:
                                    dummysequence = 'TAG'
                                else:
                                    dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                                  VALUES('{ABhit}','{genehit}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{ABhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                            f"'{genehit}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            elif allelepresent[0][0] == 1:
                                cur.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                                            f"locus='{ABhit}' AND allele_id='{genehit}' AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}')")
                                designationpresent = cur.fetchall()
                                if designationpresent[0][0] == 0:
                                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                f"allele_id, status, method, sender, "
                                                f"curator, date_entered, datestamp) "
                                                f"VALUES('{ABhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                                f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            cur2.execute(f"SELECT COUNT(*) FROM scheme_members WHERE "
                                         f"locus='{ABhit}' AND scheme_id=(SELECT id FROM schemes WHERE name='NCBI_AMR_AB')")
                            schemememberpresent = cur2.fetchall()
                            if schemememberpresent[0][0] == 0:
                                cur2.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                      VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ABhit}', 1, (SELECT CURRENT_DATE))")
                                cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                      VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ABhit}', 1, (SELECT CURRENT_DATE))")
                        elif ABpresent[0][0] == 0:
                            # seqdef db
                            cur2.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                                  VALUES('{ABhit}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                            cur2.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                  VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ABhit}', 1, (SELECT CURRENT_DATE))")
                            cur2.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                                  VALUES(1, '{ABhit}', 1, (SELECT CURRENT_DATE))")
                            cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                   VALUES('{ABhit}','{genehit}','TAG','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            # isolate db
                            dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f"{seqdefdb}",
                                                '&page=alleleInfo&locus=', f"{ABhit}", '&allele_id=[?]'])
                            cur.execute(
                                f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                                f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                                f"curator, date_entered, datestamp) \
                                                  VALUES('{ABhit}','DNA','text', 't', 't', '{seqdefdb}', '{ABhit}', "
                                f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                                f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                            cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                  VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ABhit}', 1, (SELECT CURRENT_DATE))")
                            cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                        f"allele_id, status, method, sender, "
                                        f"curator, date_entered, datestamp) "
                                        f"VALUES('{ABhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                        f"'{genehit}', 'confirmed', 'automatic', 1, "
                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                elif genedetectiondict[scheme]['schemename_bigsdb'] == 'ResFinder':
                    # gene or allele is always position 1
                    genehit = (json.loads(listofhits))[y][1].replace('.', '_').replace(' ', '_')
                    # AB from hit is always position -2
                    ABhit_s = '_'.join(['ResFinder', (json.loads(listofhits))[y][-2].upper().replace(' ', '_')])
                    for ABhit in ABhit_s.split('/'):
                        cur2.execute(f"SELECT COUNT(*) FROM loci WHERE "
                                     f"id='{ABhit}'")
                        classpresent = cur2.fetchall()
                        # if locus exists
                        if classpresent[0][0] == 1:
                            cur2.execute(f"SELECT COUNT(*) FROM sequences WHERE "
                                         f"locus='{ABhit}' AND allele_id='{genehit}'")
                            allelepresent = cur2.fetchall()
                            if allelepresent[0][0] == 0:
                                cur2.execute(
                                    f"SELECT sequence FROM sequences WHERE locus='{ABhit}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                longest_dummy_sequence = cur2.fetchall()
                                if longest_dummy_sequence == []:
                                    dummysequence = 'TAG'
                                else:
                                    dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                   VALUES('{ABhit}','{genehit}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{ABhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                            f"'{genehit}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            elif allelepresent[0][0] == 1:
                                cur.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                                            f"locus='{ABhit}' AND allele_id='{genehit}' AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}')")
                                designationpresent = cur.fetchall()
                                if designationpresent[0][0] == 0:
                                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                f"allele_id, status, method, sender, "
                                                f"curator, date_entered, datestamp) "
                                                f"VALUES('{ABhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                                f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        # else not exists; add into
                        elif classpresent[0][0] == 0:
                            # seqdef db
                            cur2.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                              VALUES('{ABhit}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                            cur2.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                              VALUES((SELECT id FROM schemes WHERE name='ResFinder_AB'), '{ABhit}', 1, (SELECT CURRENT_DATE))")
                            cur2.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                              VALUES(1, '{ABhit}', 1, (SELECT CURRENT_DATE))")
                            cur2.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                               VALUES('{ABhit}','{genehit}','TAG','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            # isolate db
                            dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f"{seqdefdb}",
                                                '&page=alleleInfo&locus=', f"{ABhit}", '&allele_id=[?]'])
                            cur.execute(
                                f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                                f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                                f"curator, date_entered, datestamp) \
                                              VALUES('{ABhit}','DNA','text', 't', 't', '{seqdefdb}', '{ABhit}', "
                                f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                                f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                            cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                              VALUES((SELECT id FROM schemes WHERE name='ResFinder_AB'), '{ABhit}', 1, (SELECT CURRENT_DATE))")
                            cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                        f"allele_id, status, method, sender, "
                                        f"curator, date_entered, datestamp) "
                                        f"VALUES('{ABhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                        f"'{genehit}', 'confirmed', 'automatic', 1, "
                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                y += 1
            eavhtmltable = eavhtmltable + '</table>'
            cur.execute(f"INSERT INTO eav_text(isolate_id, "
                        f"field, value)"
                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'),"
                        f"'{genedetectiondict[scheme]['schemename_bigsdb']}', '{eavhtmltable}') ")

            con2.close()
    cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate = '{isolate_name}'),(SELECT NOW()::TIMESTAMP), 'Gene detection results inserted', 1)")

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
            f'Error inserting output of salmonella pipeline to bigsdb for sample {isolate_name} on host {socket.gethostname()}',
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
                f'Error inserting output of salmonella pipeline to bigsdb for sample {isolate_name} on host {socket.gethostname()}',
                f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
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
                f'Error inserting output of salmonella pipeline to bigsdb for sample {isolate_name} on host {socket.gethostname()}',
                f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
    elif sample_presence[0][0] >= 1:
        sys.exit("This sample already contains typing results")

#close db connection
con.close()
