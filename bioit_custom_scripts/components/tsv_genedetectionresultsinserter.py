import json
import logging
from pathlib import Path


class TsvGeneDetectionResultsInserter:
    """
    Class containing definitions to insert gene detection results from tsv input
    """

    def __init__(self) -> None:
        pass

    def insert_genedetection_results(self, isolatename: str, species: str, genedetectiondict: dict, sample_output_dict: dict, cur_isolates: object, cur_seqdef: object) -> None:
        """
        Inserts genedetection results into bigsdb from tsv
        :param isolatename:
        :param species: commonly used bioit species name: either genus or specific like stec
        :param genedetectiondict: dictionary of species specific schemes and their properties (found in config)
        :param sample_output_dict: results of sample
        :param cur_isolates: isolate database connection object
        :param cur_seqdef: sequence definition database connection object
        :return: None
        """
        if genedetectiondict is not None:
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

                listofhits = sample_output_dict[genedetectiondict[scheme]['tsvname']].replace("'", "")
                # this might look something like this currently: [["Cluster_15", "ActA_1", "94.20", "1915/1920", "NODE_24_length_29899_cov_7.347474", "26015..27929", "NC_003210.1"], ["Cluster_59", "AgrA_1", "98.90", "729/729", "NODE_2_length_347775_cov_7.239843", "324619..325347", "NC_003210.1"], ["Cluster_67", "clpp_1", "96.82", "597/597", "NODE_5_length_187626_cov_7.284412", "124253..124849", "NC_003210.1"], ["Cluster_55", "codY_1", "95.26", "780/780", "NODE_14_length_77047_cov_5.065224", "15699..16478", "NC_003210.1"], ["Cluster_28", "ctaP_1", "97.91", "1575/1575", "NODE_8_length_111969_cov_7.509254", "4180..5754", "NC_003210.1"], ["Cluster_72", "ctsR_1", "96.95", "459/459", "NODE_3_length_239115_cov_6.610227", "396..854", "NC_003210.1"], ["Cluster_40", "dal_1", "92.32", "1107/1107", "NODE_13_length_82610_cov_5.507547", "35258..36364", "NC_003210.1"], ["Cluster_61", "degU_1", "98.84", "687/687", "NODE_5_length_187626_cov_7.284412", "72335..73021", "NC_003210.1"], ["Cluster_29", "dltA_1", "96.02", "1533/1533", "NODE_18_length_59308_cov_5.458390", "50475..52007", "NC_003210.1"]]

                if listofhits != '[]':
                    cur_isolates.execute(f"INSERT INTO eav_text_hidden(isolate_id, "
                                         f"field, value)"
                                         f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                         f"'{genedetectiondict[scheme]['schemename_bigsdb']}', '{listofhits}') ")
                    eavhtmltable = '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                    clusterhitlist = []  # in case loci that were in different clusters at some point get in the same cluster
                    y = 0
                    while y <= (len((json.loads(listofhits))) - 1):
                        # allele is always position 1 and accession is always last position (-1)
                        hit = '_'.join([(json.loads(listofhits))[y][-1], (json.loads(listofhits))[y][1]])
                        clusterhit = clusterdict[hit]
                        # append Cluster
                        eavhtmltable = eavhtmltable + ''.join(
                            ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                        # append Locus
                        if not scheme.endswith('vfdbcore'):
                            eavhtmltable = eavhtmltable + ''.join(
                                [f'<td><a href="/galaxyreports/{species}/', isolatename, '/report.html#',
                                 genedetectiondict[scheme]['schemename_html'], '" target="_blank">',
                                 (json.loads(listofhits))[y][1], '</a></td></tr>'])
                        else:
                            eavhtmltable = eavhtmltable + ''.join(
                                [f'<td><a href="/galaxyreports/{species}/', isolatename, '/report.html#',
                                 genedetectiondict[scheme]['schemename_html'], '" target="_blank">',
                                 (json.loads(listofhits))[y][-2], '</a></td></tr>'])

                        if clusterhit not in clusterhitlist:
                            cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                 f"allele_id, status, method, sender, "
                                                 f"curator, date_entered, datestamp) "
                                                 f"VALUES('{clusterhit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                 f"1, 'confirmed', 'automatic', 1, "
                                                 f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        clusterhitlist.append(clusterhit)

                        # Part 2 for the AB schemes
                        if genedetectiondict[scheme]['schemename_bigsdb'] == 'NCBI_AMR':
                            ncbi_class = ncbi_ab_class_dict[hit]
                            # gene or allele is always position 1
                            genehit = (json.loads(listofhits))[y][1].replace('.', '_').replace(' ', '_')
                            # AB from hit is always position -2
                            ab_hits = '_'.join(['NCBI_AMR', (json.loads(listofhits))[y][-2].upper().replace(' ', '_')])
                            cur_seqdef.execute(f"SELECT COUNT(*) FROM loci WHERE "
                                               f"id='{ncbi_class}'")
                            classpresent = cur_seqdef.fetchall()
                            # if locus exists (then it always exists in class because first, but not necesarily in subclass (=AB))
                            if classpresent[0][0] == 1:
                                cur_seqdef.execute(f"SELECT COUNT(*) FROM sequences WHERE "
                                                   f"locus='{ncbi_class}' AND allele_id='{genehit}'")
                                allelepresent = cur_seqdef.fetchall()
                                if allelepresent[0][0] == 0:
                                    cur_seqdef.execute(
                                        f"SELECT sequence FROM sequences WHERE locus='{ncbi_class}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                    longest_dummy_sequence = cur_seqdef.fetchall()
                                    if longest_dummy_sequence == []:
                                        dummysequence = 'TAG'
                                    else:
                                        dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                    cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                           VALUES('{ncbi_class}','{genehit}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                    cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                         f"allele_id, status, method, sender, "
                                                         f"curator, date_entered, datestamp) "
                                                         f"VALUES('{ncbi_class}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                         f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                         f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                elif allelepresent[0][0] == 1:
                                    cur_isolates.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                                                         f"locus='{ncbi_class}' AND allele_id='{genehit}' AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}')")
                                    designationpresent = cur_isolates.fetchall()
                                    if designationpresent[0][0] == 0:
                                        cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                             f"allele_id, status, method, sender, "
                                                             f"curator, date_entered, datestamp) "
                                                             f"VALUES('{ncbi_class}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                             f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                             f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            # else not exists; add into
                            elif classpresent[0][0] == 0:
                                # seqdef db
                                cur_seqdef.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                                      VALUES('{ncbi_class}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                                cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                      VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB_CLASS'), '{ncbi_class}', 1, (SELECT CURRENT_DATE))")
                                cur_seqdef.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                                      VALUES(1, '{ncbi_class}', 1, (SELECT CURRENT_DATE))")
                                cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                       VALUES('{ncbi_class}','{genehit}','TAG','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                # isolate db
                                dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{species}_seqdef',
                                                    '&page=alleleInfo&locus=', f"{ncbi_class}", '&allele_id=[?]'])
                                cur_isolates.execute(
                                    f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                                    f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                                    f"curator, date_entered, datestamp) \
                                                      VALUES('{ncbi_class}','DNA','text', 't', 't', 'bigsdb_{species}_seqdef', '{ncbi_class}', "
                                    f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                                    f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                                cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                      VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB_CLASS'), '{ncbi_class}', 1, (SELECT CURRENT_DATE))")
                                cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                     f"allele_id, status, method, sender, "
                                                     f"curator, date_entered, datestamp) "
                                                     f"VALUES('{ncbi_class}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                     f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                     f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            for ab_hit in ab_hits.split('/'):
                                cur_seqdef.execute(f"SELECT COUNT(*) FROM loci WHERE "
                                                   f"id='{ab_hit}'")
                                ab_present = cur_seqdef.fetchall()
                                # if locus exists (then it always exists in class because first, but not necesarily in subclass (=AB))
                                if ab_present[0][0] == 1:
                                    cur_seqdef.execute(f"SELECT COUNT(*) FROM sequences WHERE "
                                                       f"locus='{ab_hit}' AND allele_id='{genehit}'")
                                    allelepresent = cur_seqdef.fetchall()
                                    if allelepresent[0][0] == 0:
                                        cur_seqdef.execute(
                                            f"SELECT sequence FROM sequences WHERE locus='{ab_hit}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                        longest_dummy_sequence = cur_seqdef.fetchall()
                                        if longest_dummy_sequence == []:
                                            dummysequence = 'TAG'
                                        else:
                                            dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                        cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                                          VALUES('{ab_hit}','{genehit}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                        cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                             f"allele_id, status, method, sender, "
                                                             f"curator, date_entered, datestamp) "
                                                             f"VALUES('{ab_hit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                             f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                             f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                    elif allelepresent[0][0] == 1:
                                        cur_isolates.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                                                             f"locus='{ab_hit}' AND allele_id='{genehit}' AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}')")
                                        designationpresent = cur_isolates.fetchall()
                                        if designationpresent[0][0] == 0:
                                            cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                                 f"allele_id, status, method, sender, "
                                                                 f"curator, date_entered, datestamp) "
                                                                 f"VALUES('{ab_hit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                                 f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                                 f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                    cur_seqdef.execute(f"SELECT COUNT(*) FROM scheme_members WHERE "
                                                       f"locus='{ab_hit}' AND scheme_id=(SELECT id FROM schemes WHERE name='NCBI_AMR_AB')")
                                    schemememberpresent = cur_seqdef.fetchall()
                                    if schemememberpresent[0][0] == 0:
                                        cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                              VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                        cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                              VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                elif ab_present[0][0] == 0:
                                    # seqdef db
                                    cur_seqdef.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                                          VALUES('{ab_hit}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                                    cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                          VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                    cur_seqdef.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                                          VALUES(1, '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                    cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                           VALUES('{ab_hit}','{genehit}','TAG','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                    # isolate db
                                    dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{species}_seqdef',
                                                        '&page=alleleInfo&locus=', f"{ab_hit}", '&allele_id=[?]'])
                                    cur_isolates.execute(
                                        f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                                        f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                                        f"curator, date_entered, datestamp) \
                                                          VALUES('{ab_hit}','DNA','text', 't', 't', 'bigsdb_{species}_seqdef', '{ab_hit}', "
                                        f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                                        f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                                    cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                          VALUES((SELECT id FROM schemes WHERE name='NCBI_AMR_AB'), '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                    cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                         f"allele_id, status, method, sender, "
                                                         f"curator, date_entered, datestamp) "
                                                         f"VALUES('{ab_hit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                         f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                         f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        elif genedetectiondict[scheme]['schemename_bigsdb'] == 'ResFinder':
                            # gene or allele is always position 1
                            genehit = (json.loads(listofhits))[y][1].replace('.', '_').replace(' ', '_')
                            # AB from hit is always position -2
                            ab_hits = '_'.join(['ResFinder', (json.loads(listofhits))[y][-2].upper().replace(' ', '_')])
                            for ab_hit in ab_hits.split('/'):
                                cur_seqdef.execute(f"SELECT COUNT(*) FROM loci WHERE "
                                                   f"id='{ab_hit}'")
                                classpresent = cur_seqdef.fetchall()
                                # if locus exists
                                if classpresent[0][0] == 1:
                                    cur_seqdef.execute(f"SELECT COUNT(*) FROM sequences WHERE "
                                                       f"locus='{ab_hit}' AND allele_id='{genehit}'")
                                    allelepresent = cur_seqdef.fetchall()
                                    if allelepresent[0][0] == 0:
                                        cur_seqdef.execute(
                                            f"SELECT sequence FROM sequences WHERE locus='{ab_hit}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                        longest_dummy_sequence = cur_seqdef.fetchall()
                                        if longest_dummy_sequence == []:
                                            dummysequence = 'TAG'
                                        else:
                                            dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                        cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                           VALUES('{ab_hit}','{genehit}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                        cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                             f"allele_id, status, method, sender, "
                                                             f"curator, date_entered, datestamp) "
                                                             f"VALUES('{ab_hit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                             f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                             f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                    elif allelepresent[0][0] == 1:
                                        cur_isolates.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                                                             f"locus='{ab_hit}' AND allele_id='{genehit}' AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}')")
                                        designationpresent = cur_isolates.fetchall()
                                        if designationpresent[0][0] == 0:
                                            cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                                 f"allele_id, status, method, sender, "
                                                                 f"curator, date_entered, datestamp) "
                                                                 f"VALUES('{ab_hit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                                 f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                                 f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                # else not exists; add into
                                elif classpresent[0][0] == 0:
                                    # seqdef db
                                    cur_seqdef.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                                      VALUES('{ab_hit}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                                    cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                      VALUES((SELECT id FROM schemes WHERE name='ResFinder_AB'), '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                    cur_seqdef.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                                      VALUES(1, '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                    cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                       VALUES('{ab_hit}','{genehit}','TAG','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                    # isolate db
                                    dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{species}_seqdef',
                                                        '&page=alleleInfo&locus=', f"{ab_hit}", '&allele_id=[?]'])
                                    cur_isolates.execute(
                                        f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                                        f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                                        f"curator, date_entered, datestamp) \
                                                      VALUES('{ab_hit}','DNA','text', 't', 't', 'bigsdb_{species}_seqdef', '{ab_hit}', "
                                        f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                                        f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
                                    cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                      VALUES((SELECT id FROM schemes WHERE name='ResFinder_AB'), '{ab_hit}', 1, (SELECT CURRENT_DATE))")
                                    cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                         f"allele_id, status, method, sender, "
                                                         f"curator, date_entered, datestamp) "
                                                         f"VALUES('{ab_hit}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                         f"'{genehit}', 'confirmed', 'automatic', 1, "
                                                         f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        y += 1
                    eavhtmltable = eavhtmltable + '</table>'
                    cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                         f"field, value)"
                                         f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                         f"'{genedetectiondict[scheme]['schemename_bigsdb']}', '{eavhtmltable}') ")
            cur_isolates.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                                 f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),(SELECT NOW()::TIMESTAMP), 'Gene detection results inserted', 1)")
            logging.info('Gene detection insertion succesful')
