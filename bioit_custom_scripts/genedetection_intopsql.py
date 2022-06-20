# I will not create schemes, these have to be created by the users manually
# I will create loci/clusters in both both the seqdef and the isolate db and also put these loci/clusters
# into schemes and link the loci/clusters from isolate db to seqdef db
# I will also fill up these clusters with dummy alleles being TAG (allele id 1) and null allele (allele id 0) although null allele is not necessarily neccesary

import os
import psycopg2
from pathlib import Path
import json

schemedict = {
              'listeria_ndaro':           {'clusteredfasta': '/db/gene_detection/NCBI_AMR/ncbi_amr-clustered_80.fasta',
                                           'metadatafile': '/db/gene_detection/NCBI_AMR/mapping_full.json',
                                           'schemename_bigsdb': 'NCBI_AMR',
                                           'schemename_html': 'NCBI AMR genes',
                                           'isolatedb': 'bigsdb_listeria_isolates',
                                           'seqdefdb': 'bigsdb_listeria_seqdef',
                                           'species': 'listeria'},
              'listeria_resfinder':       {'clusteredfasta': '/db/gene_detection/ResFinder/resfinder-clustered_80.fasta',
                                           'metadatafile': '/db/gene_detection/ResFinder/mapping_full.json',
                                           'schemename_bigsdb': 'ResFinder',
                                           'schemename_html': 'ResFinder',
                                           'isolatedb': 'bigsdb_listeria_isolates',
                                           'seqdefdb': 'bigsdb_listeria_seqdef',
                                           'species': 'listeria'},
              'listeria_virulencefinder': {'clusteredfasta': '/db/gene_detection/VirulenceFinder-Listeria/virulencefinder-listeria-clustered_80.fasta',
                                           'metadatafile': '/db/gene_detection/VirulenceFinder-Listeria/mapping_full.json',
                                           'schemename_bigsdb': 'VirulenceFinder_Listeria',
                                           'schemename_html': 'VirulenceFinder - <i>Listeria</i>',
                                           'isolatedb': 'bigsdb_listeria_isolates',
                                           'seqdefdb': 'bigsdb_listeria_seqdef',
                                           'species': 'listeria'},
              'listeria_vfdbcore':        {'clusteredfasta': '/db/gene_detection/VFDB_core/vfdb_core-clustered_80.fasta',
                                           'metadatafile': '/db/gene_detection/VFDB_core/mapping_full.json',
                                           'schemename_bigsdb': 'VFDB_core',
                                           'schemename_html': 'Virulence Factor DB - Core',
                                           'isolatedb': 'bigsdb_listeria_isolates',
                                           'seqdefdb': 'bigsdb_listeria_seqdef',
                                           'species': 'listeria'},
              'listeria_plasmidfinder':   {'clusteredfasta': '/db/gene_detection/PlasmidFinder-gram_positive/plasmidfinder-gram_positive-clustered_80.fasta',
                                           'metadatafile': '/db/gene_detection/PlasmidFinder-gram_positive/mapping_full.json',
                                           'schemename_bigsdb': 'PlasmidFinder_grampositive',
                                           'schemename_html': 'PlasmidFinder - Gram positive',
                                           'isolatedb': 'bigsdb_listeria_isolates',
                                           'seqdefdb': 'bigsdb_listeria_seqdef',
                                           'species': 'listeria'},
              'neisseria_ndaro':           {'clusteredfasta': '/db/gene_detection/NCBI_AMR/ncbi_amr-clustered_80.fasta',
                                            'metadatafile': '/db/gene_detection/NCBI_AMR/mapping_full.json',
                                            'schemename_bigsdb': 'NCBI_AMR',
                                            'schemename_html': 'NCBI AMR genes',
                                            'isolatedb': 'bigsdb_neisseria_isolates',
                                            'seqdefdb': 'bigsdb_neisseria_seqdef',
                                            'species': 'neisseria'},
              'neisseria_resfinder':       {'clusteredfasta': '/db/gene_detection/ResFinder/resfinder-clustered_80.fasta',
                                            'metadatafile': '/db/gene_detection/ResFinder/mapping_full.json',
                                            'schemename_bigsdb': 'ResFinder',
                                            'schemename_html': 'ResFinder',
                                            'isolatedb': 'bigsdb_neisseria_isolates',
                                            'seqdefdb': 'bigsdb_neisseria_seqdef',
                                            'species': 'neisseria'},
              'stec_ndaro':                {'clusteredfasta': '/db/gene_detection/NCBI_AMR/ncbi_amr-clustered_80.fasta',
                                            'metadatafile': '/db/gene_detection/NCBI_AMR/mapping_full.json',
                                            'schemename_bigsdb': 'NCBI_AMR',
                                            'schemename_html': 'NCBI AMR genes',
                                            'isolatedb': 'bigsdb_stec_isolates',
                                            'seqdefdb': 'bigsdb_stec_seqdef',
                                            'species': 'stec'},
              'stec_resfinder':            {'clusteredfasta': '/db/gene_detection/ResFinder/resfinder-clustered_80.fasta',
                                            'metadatafile': '/db/gene_detection/ResFinder/mapping_full.json',
                                            'schemename_bigsdb': 'ResFinder',
                                            'schemename_html': 'ResFinder',
                                            'isolatedb': 'bigsdb_stec_isolates',
                                            'seqdefdb': 'bigsdb_stec_seqdef',
                                            'species': 'stec'},
              'stec_plasmidfinder':        {'clusteredfasta': '/db/gene_detection/PlasmidFinder-entero/plasmidfinder-entero-clustered_80.fasta',
                                            'metadatafile': '/db/gene_detection/PlasmidFinder-entero/mapping_full.json',
                                            'schemename_bigsdb': 'PlasmidFinder_entero',
                                            'schemename_html': 'PlasmidFinder - Enterobacteriaceae',
                                            'isolatedb': 'bigsdb_stec_isolates',
                                            'seqdefdb': 'bigsdb_stec_seqdef',
                                            'species': 'stec'},
              'stec_virulencefinder_ecoli': {'clusteredfasta': '/db/gene_detection/VirulenceFinder-Ecoli/virulencefinder-ecoli-clustered_80.fasta',
                                             'metadatafile': '/db/gene_detection/VirulenceFinder-Ecoli/mapping_full.json',
                                             'schemename_bigsdb': 'VirulenceFinder_Ecoli',
                                             'schemename_html': 'VirulenceFinder - <i>E. coli</i>',
                                             'isolatedb': 'bigsdb_stec_isolates',
                                             'seqdefdb': 'bigsdb_stec_seqdef',
                                             'species': 'stec'},
              'stec_virulencefinder_shiga': {'clusteredfasta': '/db/gene_detection/VirulenceFinder-Shiga/virulencefinder-shiga-clustered_80.fasta',
                                             'metadatafile': '/db/gene_detection/VirulenceFinder-Shiga/mapping_full.json',
                                             'schemename_bigsdb': 'VirulenceFinder_Shiga',
                                             'schemename_html': 'VirulenceFinder - Shiga-toxin genes',
                                             'isolatedb': 'bigsdb_stec_isolates',
                                             'seqdefdb': 'bigsdb_stec_seqdef',
                                             'species': 'stec'},
              'salmonella_ndaro': {'clusteredfasta': '/db/gene_detection/NCBI_AMR/ncbi_amr-clustered_80.fasta',
                                             'metadatafile': '/db/gene_detection/NCBI_AMR/mapping_full.json',
                                             'schemename_bigsdb': 'NCBI_AMR',
                                             'schemename_html': 'NCBI AMR genes',
                                             'isolatedb': 'bigsdb_salmonella_isolates',
                                             'seqdefdb': 'bigsdb_salmonella_seqdef',
                                             'species': 'salmonella'},
              'salmonella_resfinder': {'clusteredfasta': '/db/gene_detection/ResFinder/resfinder-clustered_80.fasta',
                                             'metadatafile': '/db/gene_detection/ResFinder/mapping_full.json',
                                             'schemename_bigsdb': 'ResFinder',
                                             'schemename_html': 'ResFinder',
                                             'isolatedb': 'bigsdb_salmonella_isolates',
                                             'seqdefdb': 'bigsdb_salmonella_seqdef',
                                             'species': 'salmonella'},
              'salmonella_plasmidfinder': {
                                             'clusteredfasta': '/db/gene_detection/PlasmidFinder-entero/plasmidfinder-entero-clustered_80.fasta',
                                             'metadatafile': '/db/gene_detection/PlasmidFinder-entero/mapping_full.json',
                                             'schemename_bigsdb': 'PlasmidFinder_entero',
                                             'schemename_html': 'PlasmidFinder - Enterobacteriaceae',
                                             'isolatedb': 'bigsdb_salmonella_isolates',
                                             'seqdefdb': 'bigsdb_salmonella_seqdef',
                                             'species': 'salmonella'},
              'salmonella_vfdbcore': {'clusteredfasta': '/db/gene_detection/VFDB_core/vfdb_core-clustered_80.fasta',
                                             'metadatafile': '/db/gene_detection/VFDB_core/mapping_full.json',
                                             'schemename_bigsdb': 'VFDB_core',
                                             'schemename_html': 'Virulence Factor DB - Core',
                                             'isolatedb': 'bigsdb_salmonella_isolates',
                                             'seqdefdb': 'bigsdb_salmonella_seqdef',
                                             'species': 'salmonella'}
              }


for scheme in schemedict:
    # Part 1 adding all the loci (clusters), scheme members and alleles (dummy boolean) in seqdef and isolate dbs
    clusterfile = open(Path(schemedict[scheme]['clusteredfasta']), 'r').readlines()
    clusterlist = []
    for line in clusterfile:
        # line looks like this: >0__Cluster_0__seq_4648__seq_4648
        if line.startswith('>'):
            clusterlist.append('_'.join([schemedict[scheme]['schemename_bigsdb'], ''.join(['Gene', line.split('__')[1]])]))
    for cluster in clusterlist:
        con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user="apache", password="remote",
                               host="127.0.0.1", port="")
        cur = con.cursor()
        con.autocommit = True
        cur.execute(f"SELECT count(*) FROM loci WHERE id='{cluster}'")
        present = cur.fetchall()
        if present[0][0] == 0:
            cur.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                              VALUES('{cluster}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
            cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                              VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{cluster}', 1, (SELECT CURRENT_DATE))")
            cur.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                              VALUES(1, '{cluster}', 1, (SELECT CURRENT_DATE))")
            cur.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                          VALUES('{cluster}',1,'TAG','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            cur.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status, sender,curator, date_entered, datestamp) \
                          VALUES('{cluster}',0, 'null allele', '',0,0,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            con.close()
            con = psycopg2.connect(database=f"{schemedict[scheme]['isolatedb']}", user="apache", password="remote",
                                   host="127.0.0.1", port="")
            cur = con.cursor()
            con.autocommit = True
            dbaseurl = ''.join(
                ['/cgi-bin/bigsdb/bigsdb.pl?db=', f"{schemedict[scheme]['seqdefdb']}", '&page=alleleInfo&locus=', f"{cluster}", '&allele_id=[?]'])
            cur.execute(
                f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                f"curator, date_entered, datestamp) \
                              VALUES('{cluster}','DNA','text', 't', 't', '{schemedict[scheme]['seqdefdb']}', '{cluster}', "
                f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
            cur.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                              VALUES((SELECT id FROM schemes WHERE name='{schemedict[scheme]['schemename_bigsdb']}'), '{cluster}', 1, (SELECT CURRENT_DATE))")
            con.close()
        else:
            continue

    #Part 2 removing and updating all allele designations (clusters) for all isolates containing data for that gene detection cluster.

    # initiate Cluster dict with description (= genes) in list format by creating empty lists
    descriptiondict = {}
    for cluster in clusterlist:
        descriptiondict[cluster] = []

    # first create a cluster content list
    sequencefile = json.load(open(Path(schemedict[scheme]['metadatafile']), 'r'))
    sequencenamedict = {}
    print(scheme)
    for x in list(sequencefile):
        # sequencename becomes accession concatenated with allele because in e.g. Resfinder, multiple accessions are not unique. Also allele is in every mapping_full.json, but not gene
        # sequencefile looks like this: {'seq_0': {'accession': 'NG_047553.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047553.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_1': {'accession': 'NG_047554.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047554.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_2': {'accession': 'NG_056058.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_056058.1_BcII', 'cluster': 'Cluster_561'}, 'seq_3': {'accession': 'NG_047221.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_047221.1_BcII', 'cluster': 'Cluster_561'}}
        # in VFDB, there are accessions with name "null", this breaks the script, therefore an empty space is added, and the allele should be enough to find.
        if sequencefile[x]['accession'] is None:
            sequencefile[x]['accession'] = ""
            print(sequencefile[x]['accession'])
        sequencenamedict[x] = '_'.join([(sequencefile[x]['accession']), (sequencefile[x]['allele']).replace("'","")])
        if schemedict[scheme]['schemename_bigsdb'] != 'VFDB_core':
            descriptiondict['_'.join([schemedict[scheme]['schemename_bigsdb'], (''.join(['Gene', sequencefile[x]['cluster']]))])].append((sequencefile[x]['allele']).replace("'",""))
        else:
            descriptiondict['_'.join([schemedict[scheme]['schemename_bigsdb'], (''.join(['Gene',sequencefile[x]['cluster']]))])].append((sequencefile[x]['gene']).replace("'", ""))
    clusterfile = open(Path(schemedict[scheme]['clusteredfasta']), 'r').readlines()
    clusterdict = {}
    for line in clusterfile:
        # line looks like this: >0__Cluster_0__seq_4648__seq_4648
        if line.startswith('>'):
            # key is sequencename from previous dict, value is cluster
            clusterdict[sequencenamedict[line.split('__')[2]]] = '_'.join([schemedict[scheme]['schemename_bigsdb'], ''.join(['Gene', line.split('__')[1]])])
            # e.g. sequencenamedict['NG_047553.11567214_ble'] = 'GeneCluster_0'


    # set the descriptions of the loci, comma separated list of all genes
    con = psycopg2.connect(database=f"{schemedict[scheme]['seqdefdb']}", user="apache", password="remote",
                           host="127.0.0.1", port="")
    cur = con.cursor()
    con.autocommit = True
    cur.execute(f"DELETE FROM locus_descriptions WHERE locus LIKE '{schemedict[scheme]['schemename_bigsdb']}_GeneCluster%'")
    for cluster, description in descriptiondict.items():
        # convert list to more meaningfull and aesthatically pleasing string
        descriptionstring = ' '.join(['Contains genes:', ', '.join([x for x in description])])
        cur.execute(f"INSERT INTO locus_descriptions(locus, product, description, datestamp, curator) "
                    f"VALUES('{cluster}', '{descriptionstring.replace('Contains genes:','')}', '{descriptionstring}' ,(SELECT CURRENT_DATE), 1)")
    con.close()


    con = psycopg2.connect(database=f"{schemedict[scheme]['isolatedb']}", user="apache", password="remote",
                           host="127.0.0.1", port="")
    cur = con.cursor()
    con.autocommit = True
    cur.execute(f"DELETE FROM allele_designations WHERE locus LIKE '{schemedict[scheme]['schemename_bigsdb']}_GeneCluster%'")
    cur.execute(f"SELECT isolate_id, value FROM eav_text_hidden WHERE field ='{schemedict[scheme]['schemename_bigsdb']}'")
    listofsamplesandhits = cur.fetchall()
    #this might look something like this currently: [(3, '[["Cluster_15", "ActA_1", "94.20", "1915/1920", "NODE_24_length_29899_cov_7.347474", "26015..27929", "NC_003210.1"], ["Cluster_59", "AgrA_1", "98.90", "729/729", "NODE_2_length_347775_cov_7.239843", "324619..325347", "NC_003210.1"], ["Cluster_67", "clpp_1", "96.82", "597/597", "NODE_5_length_187626_cov_7.284412", "124253..124849", "NC_003210.1"], ["Cluster_55", "codY_1", "95.26", "780/780", "NODE_14_length_77047_cov_5.065224", "15699..16478", "NC_003210.1"], ["Cluster_28", "ctaP_1", "97.91", "1575/1575", "NODE_8_length_111969_cov_7.509254", "4180..5754", "NC_003210.1"], ["Cluster_72", "ctsR_1", "96.95", "459/459", "NODE_3_length_239115_cov_6.610227", "396..854", "NC_003210.1"], ["Cluster_40", "dal_1", "92.32", "1107/1107", "NODE_13_length_82610_cov_5.507547", "35258..36364", "NC_003210.1"], ["Cluster_61", "degU_1", "98.84", "687/687", "NODE_5_length_187626_cov_7.284412", "72335..73021", "NC_003210.1"], ["Cluster_29", "dltA_1", "96.02", "1533/1533", "NODE_18_length_59308_cov_5.458390", "50475..52007", "NC_003210.1"]]'), (4, '["Cluster_0", "Eut_operon_1", "97.06", "15039/15038", "NODE_9_length_109885_cov_5.345642", "68077..83115", "NC_003210.1"], ["Cluster_23", "fbpA_1", "91.71", "1713/1713", "NODE_1_length_368586_cov_5.801544", "317694..319406", "NC_003210.1"], ["Cluster_53", "FlaA_1", "98.15", "864/864", "NODE_16_length_63978_cov_5.528441", "47023..47886", "NC_003210.1"], ["Cluster_38", "FlgE_1", "94.01", "1236/1236", "NODE_16_length_63978_cov_5.528441", "41031..42266", "NC_003210.1"], ["Cluster_76", "FlgC_1", "92.46", "411/411", "NODE_16_length_63978_cov_5.528441", "29381..29791", "NC_003210.1"], ["Cluster_70", "fri_1", "97.86", "467/471", "NODE_27_length_26080_cov_5.738643", "7405..7871", "NC_003210.1"], ["Cluster_73", "fur_1", "96.25", "453/453", "NODE_1_length_368586_cov_5.801544", "184454..184906", "NC_003210.1"], ["Cluster_16", "Gmar_1", "96.97", "1914/1914", "NODE_16_length_63978_cov_5.528441", "49045..50958", "NC_017537.1"], ["Cluster_79", "hfq_1", "99.14", "234/234", "NODE_14_length_77047_cov_5.065224", "32920..33153", "NC_003210.1"]')]
    x = 0
    if len(listofsamplesandhits) != 0:
        while x <= (len(listofsamplesandhits) - 1):
            isolate_id = listofsamplesandhits[x][0]
            cur.execute(f"SELECT isolate FROM isolates WHERE id ='{isolate_id}'")
            isolate_name = cur.fetchall()[0][0]
            eavhtmltable = '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
            clusterhitlist = []  # in case loci that were in different clusters at some point get in the same cluster
            y = 0
            while y <= (len(json.loads(listofsamplesandhits[x][1])) - 1):
                # allele is always position 1 and accession is always last position (-1)
                hit = '_'.join([(json.loads(listofsamplesandhits[x][1]))[y][-1], (json.loads(listofsamplesandhits[x][1]))[y][1]])
                clusterhit = clusterdict[hit]
                # append Cluster
                eavhtmltable = eavhtmltable + ''.join(['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                # append Locus
                if scheme != 'vfdb_core':
                    eavhtmltable = eavhtmltable + ''.join(['<td><a href="/galaxyreports/', schemedict[scheme]['species'], '/', isolate_name, '/report.html#', schemedict[scheme]['schemename_html'], '" target="_blank">', (json.loads(listofsamplesandhits[x][1]))[y][1], '</a></td></tr>'])
                else:
                    eavhtmltable = eavhtmltable + ''.join(['<td><a href="/galaxyreports/', schemedict[scheme]['species'], '/', isolate_name, '/report.html#', schemedict[scheme]['schemename_html'], '" target="_blank">', (json.loads(listofsamplesandhits[x][1]))[y][-2], '</a></td></tr>'])

                if clusterhit not in clusterhitlist:
                    cur.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                f"allele_id, status, method, sender, "
                                f"curator, date_entered, datestamp) "
                                f"VALUES('{clusterhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolate_name}'), "
                                f"1, 'confirmed', 'automatic', 1, "
                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                clusterhitlist.append(clusterhit)
                y += 1
            eavhtmltable = eavhtmltable + '</table>'
            cur.execute(f"DELETE FROM eav_text WHERE isolate_id = '{isolate_id}' AND field ='{schemedict[scheme]['schemename_bigsdb']}'")
            cur.execute(f"INSERT INTO eav_text(isolate_id, "
                        f"field, value)"
                        f"VALUES('{isolate_id}',"
                        f"'{schemedict[scheme]['schemename_bigsdb']}', '{eavhtmltable}') ")
            x += 1
            cur.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                        f"VALUES('{isolate_id}',(SELECT NOW()::TIMESTAMP), 'Gene detection results reevaluated after database update', 1)")

con.close()