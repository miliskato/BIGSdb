import os
import sys
import psycopg2
import argparse
from pathlib import Path
import json

schemedict = {'listeria_mlst': {'dirdb': '/db/sequence_typing/listeria/mlst', 'tsvname': 'mlst'},
              'listeria_cgmlst': {'dirdb': '/db/sequence_typing/listeria/cgmlst', 'tsvname': 'cgmlst'},
              'listeria_serogroup': {'dirdb': '/db/sequence_typing/listeria/serogroup', 'tsvname': 'pcr_serogroup'},
              'listeria_metal_detergent_resistance': {'dirdb': '/db/sequence_typing/listeria/metal_detergent_resistance', 'tsvname': 'metal_detergent'},
              'listeria_typing_virulence': {'dirdb': '/db/sequence_typing/listeria/virulence', 'tsvname': 'typing_virulence'},
              'listeria_antibiotic_resistance': {'dirdb': '/db/sequence_typing/listeria/antibiotic_resistance', 'tsvname': 'typing_amr'},
              'listeria_species_confirmation': {'dirdb': '/db/sequence_typing/listeria/species_confirmation', 'tsvname': 'species_confirmation'}
              }
genedetectiondict = {'listeria_ndaro':
                         {'clusteredfasta': '/db/gene_detection/NCBI_AMR/ncbi_amr_upd-clustered_80.fasta',
                          'metadatafile': '/db/gene_detection/NCBI_AMR/mapping_full.json',
                          'tsvname': 'hits_ncbi_amr',
                          'schemename_bigsdb': 'NCBI_AMR',
                          'schemename_html': 'NCBI AMR genes'},
                     'listeria_resfinder': {
                         'clusteredfasta': '/db/gene_detection/ResFinder/resfinder-clustered_80.fasta',
                         'metadatafile': '/db/gene_detection/ResFinder/mapping_full.json',
                         'tsvname': 'hits_resfinder',
                         'schemename_bigsdb': 'ResFinder',
                         'schemename_html': 'ResFinder'},
                     'listeria_virulencefinder': {
                         'clusteredfasta': '/db/gene_detection/VirulenceFinder-Listeria/virulencefinder-listeria-clustered_80.fasta',
                         'metadatafile': '/db/gene_detection/VirulenceFinder-Listeria/mapping_full.json',
                         'tsvname': 'hits_virulencefinder',
                         'schemename_bigsdb': 'VirulenceFinder_Listeria',
                         'schemename_html': 'VirulenceFinder - <i>Listeria</i>'},
                     'listeria_vfdbcore': {
                         'clusteredfasta': '/db/gene_detection/VFDB_core/vfdb_core-clustered_80.fasta',
                         'metadatafile': '/db/gene_detection/VFDB_core/mapping_full.json',
                         'tsvname': 'hits_vfdb_core',
                         'schemename_bigsdb': 'VFDB_core',
                         'schemename_html': 'Virulence Factor DB - Core'},
                     'listeria_plasmidfinder': {
                         'clusteredfasta': '/db/gene_detection/PlasmidFinder-entero/plasmidfinder-entero-clustered_80.fasta',
                         'metadatafile': '/db/gene_detection/PlasmidFinder-entero/mapping_full.json',
                         'tsvname': 'hits_plasmidfinder',
                         'schemename_bigsdb': 'PlasmidFinder_entero',
                         'schemename_html': 'PlasmidFinder - Gram positive'}
                     }

isolatedb = 'bigsdb_listeria_isolates'

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--tsvfilepath', required=True, type=Path)
argument_parser.add_argument('--isolatename', required=True, type=str)
args = argument_parser.parse_args()
tsvfilepath = Path(args.tsvfilepath)
isolate_name = args.isolatename

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
    reportlink =f'<p><a href="/galaxyreports/listeria/{isolate_name}/report.html"> html report</a></p>'
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'html', '{reportlink}') ")
    cur.execute(f"INSERT INTO eav_text(isolate_id, "
                f"field, value)"
                f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                f"'tsv', '{reportlink.replace('html', 'tsv')}') ")
    dirlist = [] #dirlist serves to not insert duplicates (creates error in sql), for Listeria e.g. prs and prfA are included in two schemes
    for scheme in schemedict:
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

                # the elif below is specific to Listeria pcr serogroup where 0's are included in the profiles
                # (absent loci are required to define profiles)
                # Bigsdb creates a null allele itself in the seqdef database
                elif result[2] == '-' and result[3] == '-' and dir in next(os.walk(schemedict['listeria_serogroup']['dirdb']))[1]:
                    allele_id = 0
                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                f"allele_id, status, method, sender, "
                                f"curator, date_entered, datestamp) "
                                f"VALUES('{dir}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                                f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                else:
                    continue

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

for scheme in genedetectiondict:
    # todo check whether contains gene detection allele designations already, but already does this in function above, so would only be useful if this for loop secifically is run
    # first create a cluster content list
    sequencefile = json.load(open(Path(genedetectiondict[scheme]['metadatafile']), 'r'))
    sequencenamedict = {}
    for x in list(sequencefile):
        # sequencename becomes accession concatenated with allele because in e.g. Resfinder, multiple accessions are not unique.
        # sequencefile looks like this: {'seq_0': {'accession': 'NG_047553.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047553.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_1': {'accession': 'NG_047554.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047554.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_2': {'accession': 'NG_056058.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_056058.1_BcII', 'cluster': 'Cluster_561'}, 'seq_3': {'accession': 'NG_047221.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_047221.1_BcII', 'cluster': 'Cluster_561'}}
        # in VFDB, there are accessions with name "null", this breaks the script, therefore an empty space is added, and the allele should be enough to find.
        if sequencefile[x]['accession'] is None:
            sequencefile[x]['accession'] = ""
            print(sequencefile[x]['accession'])
        sequencenamedict[x] = '_'.join([(sequencefile[x]['accession']), (sequencefile[x]['allele'])])

    clusterfile = open(Path(genedetectiondict[scheme]['clusteredfasta']), 'r').readlines()
    clusterdict = {}
    for line in clusterfile:
        # line looks like this: >0__Cluster_0__seq_4648__seq_4648
        if line.startswith('>'):
            # key is sequencename from previous dict, value is cluster
            clusterdict[sequencenamedict[line.split('__')[2]]] = '_'.join([genedetectiondict[scheme]['schemename_bigsdb'], line.split('__')[1]])
            # e.g. sequencenamedict['NG_047553.11567214_ble'] = 'NCBIAMR_Cluster_0'

    con = psycopg2.connect(database=f"{isolatedb}", user="apache", password="remote",
                           host="127.0.0.1", port="")
    cur = con.cursor()
    con.autocommit = True
    listofhits = outputtsvdict[genedetectiondict[scheme]['tsvname']]
    #this might look something like this currently: [["Cluster_15", "ActA_1", "94.20", "1915/1920", "NODE_24_length_29899_cov_7.347474", "26015..27929", "NC_003210.1"], ["Cluster_59", "AgrA_1", "98.90", "729/729", "NODE_2_length_347775_cov_7.239843", "324619..325347", "NC_003210.1"], ["Cluster_67", "clpp_1", "96.82", "597/597", "NODE_5_length_187626_cov_7.284412", "124253..124849", "NC_003210.1"], ["Cluster_55", "codY_1", "95.26", "780/780", "NODE_14_length_77047_cov_5.065224", "15699..16478", "NC_003210.1"], ["Cluster_28", "ctaP_1", "97.91", "1575/1575", "NODE_8_length_111969_cov_7.509254", "4180..5754", "NC_003210.1"], ["Cluster_72", "ctsR_1", "96.95", "459/459", "NODE_3_length_239115_cov_6.610227", "396..854", "NC_003210.1"], ["Cluster_40", "dal_1", "92.32", "1107/1107", "NODE_13_length_82610_cov_5.507547", "35258..36364", "NC_003210.1"], ["Cluster_61", "degU_1", "98.84", "687/687", "NODE_5_length_187626_cov_7.284412", "72335..73021", "NC_003210.1"], ["Cluster_29", "dltA_1", "96.02", "1533/1533", "NODE_18_length_59308_cov_5.458390", "50475..52007", "NC_003210.1"]]

    if listofhits != '[]':
        cur.execute(f"INSERT INTO eav_text_hidden(isolate_id, "
                    f"field, value)"
                    f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                    f"'{genedetectiondict[scheme]['schemename_bigsdb']}', '{listofhits}') ")
        eavhtmltable= '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
        clusterhitlist = []  # in case loci that were in different clusters at some point get in the same cluster
        y = 0
        while y <= (len((json.loads(listofhits)))-1):
            # allele is always position 1 and accession is always last position (-1)
            hit = '_'.join([(json.loads(listofhits))[y][-1], (json.loads(listofhits))[y][1]])
            clusterhit = clusterdict[hit]
            # append Cluster
            eavhtmltable= eavhtmltable + ''.join(['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
            # append Locus
            if scheme != 'listeria_vfdbcore':
                eavhtmltable = eavhtmltable + ''.join(['<td><a href="/galaxyreports/listeria/', isolate_name, '/report.html#', genedetectiondict[scheme]['schemename_html'], '" target="_blank">', (json.loads(listofhits))[y][1], '</a></td></tr>'])
            else:
                eavhtmltable = eavhtmltable + ''.join(['<td><a href="/galaxyreports/listeria/', isolate_name, '/report.html#', genedetectiondict[scheme]['schemename_html'], '" target="_blank">', (json.loads(listofhits))[y][-2], '</a></td></tr>'])

            if clusterhit not in clusterhitlist:
                cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                            f"allele_id, status, method, sender, "
                            f"curator, date_entered, datestamp) "
                            f"VALUES('{clusterhit}', (SELECT id FROM isolates WHERE isolate='{isolate_name}'), "
                            f"1, 'confirmed', 'automatic', 1, "
                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            clusterhitlist.append(clusterhit)
            y += 1
        eavhtmltable= eavhtmltable + '</table>'
        cur.execute(f"INSERT INTO eav_text(isolate_id, "
                    f"field, value)"
                    f"VALUES((SELECT id FROM isolates WHERE isolate='{isolate_name}'),"
                    f"'{genedetectiondict[scheme]['schemename_bigsdb']}', '{eavhtmltable}') ")

cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
            f"VALUES((SELECT id FROM isolates WHERE isolate = '{isolate_name}'),(SELECT NOW()::TIMESTAMP), 'Gene detection results inserted', 1)")

# close db connection
con.close()
