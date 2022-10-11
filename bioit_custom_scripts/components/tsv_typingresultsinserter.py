import os
import json
import requests
import re
import ast
import logging

class TsvTypingResultsInserter:
    """
    Class containing definitions to insert typing results from tsv input
    """

    def __init__(self):
        pass

    def insert_typing_results(self, isolatename, species, schemedict, sample_output_dict, cur_isolates, cur_seqdef) -> None:
        """
        Inserts typing results into bigsdb from tsv
        :param isolatename:
        :param species:
        :param schemedict: dictionary of species specific schemes and their properties (found in config)
        :param sample_output_dict: results of sample
        :param cur_isolates: isolate database connection object
        :param cur_seqdef: sequence definition database connection object
        :return:
        """

        dirlist = []
        # dirlist serves as to not insert duplicates (creates error in sql),
        # for Listeria e.g. prs and prfA are included in two schemes
        for scheme in schemedict:
            if schemedict[scheme]['dirdb'] != '':
                dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
                for directory in dirs:
                    if not directory.startswith('.') and directory not in dirlist:
                        if directory == "rplF":  # neisseria specific
                            directory = "'rplF"
                        dirlist.append(directory)
                        result = sample_output_dict['-'.join([schemedict[scheme]['tsvname'], directory])].split(',')
                        if directory == "'rplF":  # neisseria specific
                            directory = "rplF"
                        if result[2] == '100.00' and result[3] != '-' and eval(result[3]) == 1.0:
                            allele_id = result[1]
                            cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                 f"allele_id, status, method, sender, "
                                                 f"curator, date_entered, datestamp) "
                                                 f"VALUES('{directory}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                 f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                                 f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                        # the elif below is specific to Listeria pcr serogroup where 0's are included in the profiles
                        # (absent loci are required to define profiles)
                        # Bigsdb creates a null allele itself in the seqdef database
                        elif result[2] == '-' and result[3] == '-' and (('listeria_serogroup' in schemedict.keys() and directory in \
                                next(os.walk(schemedict['listeria_serogroup']['dirdb']))[1]) or directory == 'NadA_peptide'):
                            allele_id = 0
                            cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                        f"allele_id, status, method, sender, "
                                        f"curator, date_entered, datestamp) "
                                        f"VALUES('{directory}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                        f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            elif schemedict[scheme]['dirdb'] == '':
                if scheme.endswith('pointfinder'):
                    # for pointfinder, only hits that infer resistance are of importance, other hits dont give any information.
                    listofhits = sample_output_dict[schemedict[scheme]['tsvname']]
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
                                    antibiotic_reformatted = '_'.join(
                                        ['POINTFINDER', antibiotic.replace('-', '_').replace(' ', '_').upper()])
                                    mutation = hit[0].replace('.', '_').replace(' ', '_')
                                    eavhtmltable = eavhtmltable + ''.join(
                                        [f'<tr><td><a href="/galaxyreports/{species}/', isolatename,
                                         '/report.html#',
                                         schemedict[scheme]['schemename_html'], '" target="_blank">',
                                         hit[0], '</a></td>'])
                                    eavhtmltable = eavhtmltable + ''.join(['<td>', antibiotic, '</td></tr>'])
                                    cur_seqdef.execute(
                                        f"SELECT allele_id FROM sequences WHERE allele_id = '{mutation}' and locus = '{antibiotic_reformatted}'")
                                    present = cur_seqdef.fetchall()
                                    if present == []:
                                        cur_seqdef.execute(
                                            f"SELECT sequence FROM sequences WHERE locus  ='{antibiotic_reformatted}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                        longest_dummy_sequence = cur_seqdef.fetchall()
                                        if longest_dummy_sequence == []:
                                            dummysequence = 'TAG'
                                        else:
                                            dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                        cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                       VALUES('{antibiotic_reformatted}','{mutation}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                    cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                f"allele_id, status, method, sender, "
                                                f"curator, date_entered, datestamp) "
                                                f"VALUES('{antibiotic_reformatted}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                f"'{mutation}', 'confirmed', 'automatic', 1, "
                                                f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            y += 1
                        eavhtmltable = eavhtmltable + '</table>'
                        cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                    f"field, value)"
                                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                    f"'pointfinder_hits', '{eavhtmltable}') ")
                if species == 'mycobacterium':
                    if schemedict[scheme]['dirdb'] == '':
                        if schemedict[scheme]['tsvname'] == 'spoligotype_binary' and schemedict[scheme]['tsvname'] in sample_output_dict:
                            x = 1
                            for allele_id in list(sample_output_dict[schemedict[scheme]['tsvname']]):
                                locus = ''.join(['Spacer', str(x).zfill(2)])
                                x += 1
                                cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{locus}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                            f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                        f"field, value)"
                                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                        f"'spoligotype_binary', '{sample_output_dict['spoligotype_binary']}') ")
                            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                        f"field, value)"
                                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                        f"'spoligotype_octal', '{sample_output_dict['spoligotype_octal']}') ")
                    elif scheme == 'mycobacterium_csbrd' and 'csb_detected' in sample_output_dict:
                        for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                            locus = record.rstrip(
                                '_detected')  # need to be careful with rstrip and strip but in this case no issue
                            if sample_output_dict[record] == 'False':
                                allele_id = 0
                            elif sample_output_dict[record] == 'True':
                                allele_id = 1
                            cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                        f"allele_id, status, method, sender, "
                                        f"curator, date_entered, datestamp) "
                                        f"VALUES('{locus}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                        f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                    elif scheme == 'mycobacterium_amrdetection':
                        # make a dict with field and tsv names to be able to insert
                        cur_isolates.execute(f"SELECT field FROM eav_fields WHERE category='AMR detection'")
                        fields = cur_isolates.fetchall()
                        amr_metadata_fields_tsv = {}
                        for field in fields:
                            if field[0].startswith('amr'):
                                amr_metadata_fields_tsv[field[0]] = field[0]
                            else:
                                amr_metadata_fields_tsv[field[0]] = ''.join(['amr_pheno_', field[0].split('_')[-1]])
                        for bigsdbname, tsvname in amr_metadata_fields_tsv.items():
                            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                        f"field, value)"
                                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                        f"'{bigsdbname}', '{sample_output_dict[tsvname]}') ")
                        # AMR results
                        cur_isolates.execute(
                            f"SELECT locus FROM scheme_members WHERE scheme_id = (SELECT id FROM schemes WHERE name = 'AMR_detection_WHO')")
                        loci = cur_isolates.fetchall()
                        for locus in loci:
                            tsvname = '_'.join(['amr_mutations', str(locus[0]).replace('_int', '_(int.)')])
                            if sample_output_dict[tsvname] != '-':
                                for variant in sample_output_dict[tsvname].split(', '):
                                    variantreformatted = variant.replace('(', '').replace(')', '')
                                    # Bert explained that if the change is found in promotor, then it can change signs
                                    # And also honestly the db is really discrepant, e.g. how likely is this:
                                    # Rv1979c AA G_107_A Rv1979c_AA_G_107_A Uncertain significance CFZ CFZ_Uncertain_significance
                                    # Rv1979c PROM g_-107_a Rv1979c_PROM_g_-107_a Uncertain significance CFZ CFZ_Uncertain_significance
                                    # + there are really just duplicates in the db so I limit to 1, then its always the same.
                                    cur_seqdef.execute(
                                        f"SELECT allele_id FROM sequences WHERE allele_id = '{variantreformatted}' AND locus = '{locus[0]}' LIMIT 1")
                                    present = cur_seqdef.fetchall()
                                    # Sometimes not only the sign changes when its in a promotor, but also the location, easiest solution is just to insert after it is found. Because sequences need to be unique for a locus, I take the longest sequence and add TAG
                                    if present == []:
                                        cur_seqdef.execute(
                                            f"SELECT sequence FROM sequences WHERE locus = '{locus[0]}' ORDER BY sequence DESC LIMIT 1")
                                        possiblelongestdummypresent = cur_seqdef.fetchall()
                                        if possiblelongestdummypresent == []:
                                            dummysequence = 'TAG'
                                        else:
                                            dummysequence = ''.join([possiblelongestdummypresent[0][0], 'TAG'])
                                        cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                       VALUES('{locus[0]}','{variantreformatted}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                        cur_seqdef.execute(
                                            f"SELECT allele_id FROM sequences WHERE allele_id LIKE '{variantreformatted}' AND locus = '{locus[0]}' LIMIT 1")
                                        present = cur_seqdef.fetchall()
                                    allele_id = present[0][0]
                                    cur_isolates.execute(f"SELECT FROM allele_designations WHERE locus = '{locus[0]}' AND "
                                                f"isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}') AND"
                                                f" allele_id = '{allele_id}'")
                                    allele_designation_presence = cur_isolates.fetchall()
                                    if allele_designation_presence == []:
                                        cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                    f"allele_id, status, method, sender, "
                                                    f"curator, date_entered, datestamp) "
                                                    f"VALUES('{locus[0]}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                    f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                                    f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                    elif scheme == 'mycobacterium_hsp65':
                        listofhits = sample_output_dict[schemedict[scheme]['tsvname']]
                        # this might look something like this currently: [["Cluster_0", "seq_132", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. tuberculosis", "ATCC 27294, H37Rv(T)"], ["Cluster_0", "seq_19", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. bovis", "CIP 105234(T)"], ["Cluster_0", "seq_23", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. caprae", "CIP 105776(T)"], ["Cluster_0", "seq_81", "100.00", "401/401", "NODE_2_length_176306_cov_25.596655", "48299..48699", "M. microti", "CIP 104256, ATCC 19422(T)"]]
    
                        if listofhits != '[]':
                            y = 0
                            while y <= (len((json.loads(listofhits))) - 1):
                                hit = '_'.join(['hsp65', (json.loads(listofhits))[y][-2].strip('"').replace(' ',
                                                                                                            '_').replace(
                                    '.', '')])
                                cur_isolates.execute(
                                    f"SELECT FROM eav_boolean WHERE isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}')"
                                    f" AND field = '{hit}'")
                                presence_hsp65 = cur_isolates.fetchall()
                                if presence_hsp65 == []:
                                    cur_isolates.execute(f"INSERT INTO eav_boolean(isolate_id, "
                                                f"field, value)"
                                                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                                f"'{hit}', 't') ")
                                y += 1

                    elif scheme == 'mycobacterium_ncbi16s':
                        # ncbi 16s contains duplicate species
                        listofhits = sample_output_dict[schemedict[scheme]['tsvname']]
                        # this might look like this: [["Cluster_24", "NR_044826.2", "100.00", "1532/1532", "NODE_59_length_20721_cov_23.830436", "2360..3891", "Mycobacterium tuberculosis strain H37Rv 16S ribosomal RNA, complete sequence", "NR_044826.2"], ["Cluster_24", "NR_102810.2", "100.00", "1532/1532", "NODE_59_length_20721_cov_23.830436", "2360..3891", "Mycobacterium tuberculosis strain H37Rv 16S ribosomal RNA, complete sequence", "NR_102810.2"]]
                        speciesandstrainhits = []
                        if listofhits != '[]':
                            for hit in json.loads(listofhits):
                                speciesname = '_'.join([hit[-2].split(' ')[0], hit[-2].split(' ')[1]])
                                if speciesname not in speciesandstrainhits:
                                    speciesandstrainhits.append(speciesname)
                                strainname = '_'.join(
                                    [hit[-2].split(' ')[0], hit[-2].split(' ')[1], hit[-2].split(' ')[2],
                                     hit[-2].split(' ')[3]])
                                if strainname not in speciesandstrainhits:
                                    speciesandstrainhits.append(strainname)
                        for hit in speciesandstrainhits:
                            hit_formatted = '_'.join(['ncbi16s', hit])
                            # check whether already exists in eav
                            cur_isolates.execute(
                                f"SELECT count(*) FROM eav_fields WHERE category='NCBI 16S' AND field = '{hit_formatted}'")
                            eav_exists = cur_isolates.fetchall()
                            if eav_exists[0][0] == 0:
                                cur_isolates.execute(
                                    f"INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) VALUES('{hit_formatted}', 'boolean', 'NCBI 16S', '', 't', 't', (SELECT CURRENT_DATE), 1)")
                            cur_isolates.execute(f"INSERT INTO eav_boolean(isolate_id, "
                                        f"field, value)"
                                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                        f"'{hit_formatted}', 't') ")
                elif species == 'neisseria':
                    if schemedict[scheme]['tsvname'] == 'resistance_genes':
                        for directory in ['penA', 'rpoB']:
                            result = sample_output_dict['-'.join([schemedict[scheme]['tsvname'], directory])].split(',')
                            if result[2] == '100.00' and result[3] != '-' and eval(result[3]) == 1.0:
                                allele_id = int(result[1])
                                response = requests.get(
                                    f"https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/loci/{directory}/alleles/{allele_id}")
                                json_data = response.json()
                                if json_data['status'] != '404':
                                    if json_data.get('linked_data'):
                                        if 'PubMLST isolates' in json_data['linked_data']:
                                            for antibiotic in ['rifampicin_SIR', 'penicillin_SIR']:
                                                if antibiotic in json_data['linked_data']['PubMLST isolates']:
                                                    for record in json_data['linked_data']['PubMLST isolates'][
                                                        antibiotic]:
                                                        if record['value'] == 'S':
                                                            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                                                        f"field, value)"
                                                                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                                                        f"'{'_'.join([antibiotic, 'S', 'frequency'])}', '{record['frequency']}') ")
                                                        elif record['value'] == 'R':
                                                            cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                                                        f"field, value)"
                                                                        f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                                                        f"'{'_'.join([antibiotic, 'R', 'frequency'])}', '{record['frequency']}') ")
    
                    cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                f"field, value)"
                                f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),"
                                f"'Serogroup', '{sample_output_dict['detected_serogroup']}') ")
                elif species == 'salmonella':
                    if scheme == 'salmonella_genotyphi' and 'genotyphi_lineage' in sample_output_dict:
                        cur_isolates.execute(f"SELECT field FROM eav_fields WHERE field like 'genotyphi%'")
                        genotyphi_susc_list = cur_isolates.fetchall()
                        for item in genotyphi_susc_list:
                            if item[0] in sample_output_dict:
                                susceptibility = sample_output_dict[item[0]]
                                cur_isolates.execute(
                                    f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),'{item[0]}','{susceptibility}')")
                                # insert new alleles
                                variant = item[0].replace('susceptibility', 'variants')
                                gene = item[0].replace('susceptibility', 'genes')
                                genotyphi_field = item[0].replace('_susceptibility', '').upper()
                                # get the genes and variants
                                future_alleles = sample_output_dict[variant].split(';') + sample_output_dict[gene].split(';')
                                for i in range(0, len(future_alleles)):
                                    if future_alleles[i] != '-':
                                        cur_seqdef.execute(
                                            f"SELECT allele_id FROM sequences WHERE allele_id = '{future_alleles[i]}' and locus = '{genotyphi_field}'")
                                        present_genotyphi = cur_seqdef.fetchall()
                                        if present_genotyphi == []:
                                            cur_seqdef.execute(
                                                f"SELECT sequence FROM sequences WHERE locus  ='{genotyphi_field}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                            longest_dummy_sequence = cur_seqdef.fetchall()
                                            if longest_dummy_sequence == []:
                                                dummysequence = 'TAG'
                                            else:
                                                dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                            cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                                             VALUES('{genotyphi_field}','{future_alleles[i]}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                        cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                    f"allele_id, status, method, sender, "
                                                    f"curator, date_entered, datestamp) "
                                                    f"VALUES('{genotyphi_field}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                    f"'{future_alleles[i]}', 'confirmed', 'automatic', 1, "
                                                    f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                    elif scheme == 'salmonella_serotyping':
                        cur_isolates.execute(f"SELECT field FROM eav_fields WHERE category = 'Serotyping' ")
                        serotyping_list = cur_isolates.fetchall()
                        for sero in serotyping_list:
                            tool = re.sub('_[a-z]*$', '', sero[0])
                            field_type = sero[0].split('_')[len(sero[0].split('_')) - 1]

                            # class for serotyping formula processing.
                            class formula:
                                def __init__(self, rawFormula, tool, isolatename):
                                    self.antigens = {"O_antigen": rawFormula.split(':')[0].split(','),
                                                     "H1_antigen": rawFormula.split(':')[1].split(','),
                                                     "H2_antigen": rawFormula.split(':')[2].split(',')}
                                    self.tool = tool
                                    self.isolatename = isolatename

                                def __check_if_exist_in_seqdef(self, field, entry):
                                    cur_seqdef.execute(
                                        f"SELECT allele_id FROM sequences WHERE allele_id = '{entry}' and locus = '{field}'")
                                    return (cur_seqdef.fetchall())

                                def __generate_dummy_sequence(self, field):
                                    cur_seqdef.execute(
                                        f"SELECT sequence FROM sequences WHERE locus  ='{field}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                    longest_dummy_sequence = cur_seqdef.fetchall()
                                    if longest_dummy_sequence == []:
                                        dummysequence = 'TAG'
                                    else:
                                        dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                    return dummysequence

                                def insert_antigens_into_db(self):
                                    antigens = ["O_antigen", "H1_antigen", "H2_antigen"]
                                    for antigen in antigens:
                                        field = (f'{self.tool}_{antigen}').upper()
                                        entries = self.antigens[antigen]
                                        for entry in entries:
                                            if entry != '-':
                                                presence = self.__check_if_exist_in_seqdef(field, entry)
                                                if presence == []:
                                                    dummysequence = self.__generate_dummy_sequence(field)
                                                    cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                                                                                          VALUES('{field}','{entry}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                                cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                            f"allele_id, status, method, sender, "
                                                            f"curator, date_entered, datestamp) "
                                                            f"VALUES('{field}', (SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'), "
                                                            f"'{entry}', 'confirmed', 'automatic', 1, "
                                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                            if tool == 'sistr':
                                if field_type == 'formula':
                                    if f'{tool}_serotype_antigenic_formula' in sample_output_dict:
                                        serotypingInsert = sample_output_dict[f'{tool}_serotype_antigenic_formula']
                                        if serotypingInsert != '-':
                                            sistr_formula = formula(serotypingInsert, tool, isolatename)
                                            sistr_formula.insert_antigens_into_db()
                                            cur_isolates.execute(
                                                f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),'{sero[0]}','{serotypingInsert}')")
                                elif field_type == 'serotype':
                                    if f'{tool}_serotype_concensus' in sample_output_dict:
                                        serotypingInsert = sample_output_dict[f'{tool}_serotype_concensus']
                                        if serotypingInsert != '-':
                                            cur_isolates.execute(
                                                f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),'{sero[0]}','{serotypingInsert}')")
                            else:
                                if field_type == 'formula' and f'{tool}_Predicted_antigenic_profile' in sample_output_dict:
                                    serotypingInsert = sample_output_dict[f'{tool}_Predicted_antigenic_profile']
                                    seqsero_formula = formula(serotypingInsert, tool, isolatename)
                                    seqsero_formula.insert_antigens_into_db()
                                    if serotypingInsert != '-:-:-':
                                        cur_isolates.execute(
                                            f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),'{sero[0]}','{serotypingInsert}')")
                                elif field_type == 'serotype' and f'{tool}_Predicted_serotype' in sample_output_dict:
                                    serotypingInsert = sample_output_dict[f'{tool}_Predicted_serotype']
                                    if serotypingInsert != '- -:-:-':
                                        cur_isolates.execute(
                                            f"INSERT INTO eav_text(isolate_id, field, value) VALUES ((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),'{sero[0]}','{serotypingInsert}')")

                    elif scheme == 'salmonella_spifinder':
                        schemes_spifinder = ['spifinder_fastq', 'spifinder_fasta']
                        for scheme in schemes_spifinder:
                            if scheme in sample_output_dict:
                                hits = sample_output_dict[scheme]
                                if hits != '[]':
                                    hits = ast.literal_eval(hits)
                                    for l in range(0, len(hits)):
                                        if scheme == 'spifinder_fastq':
                                            spifinder_entry = f"CatFunc{hits[l][5]}__{hits[l][3]}"
                                        else:
                                            spifinder_entry = f"CatFunc{hits[l][7]}__{hits[l][5]}"
                                        spifinder_field = f"{scheme}_{hits[l][0]}".upper()
                                        cur_seqdef.execute(
                                            f"SELECT allele_id FROM sequences WHERE allele_id = '{spifinder_entry}' and locus = '{spifinder_field}'")
                                        present_spifinder = cur_seqdef.fetchall()
                                        if present_spifinder == []:
                                            cur_seqdef.execute(
                                                f"SELECT sequence FROM sequences WHERE locus  ='{spifinder_field}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                            longest_dummy_sequence = cur_seqdef.fetchall()
                                            if longest_dummy_sequence == []:
                                                dummysequence = 'TAG'
                                            else:
                                                dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                            cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                            VALUES('{spifinder_field}','{spifinder_entry}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                        cur_isolates.execute(
                                            f"SELECT FROM allele_designations WHERE locus = '{spifinder_field}' AND "
                                            f" isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}')"
                                            f" AND allele_id = '{spifinder_entry}'")
                                        presence_allele_designation = cur_isolates.fetchall()
                                        if presence_allele_designation == []:
                                            cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                                        f"allele_id, status, method, sender, "
                                                        f"curator, date_entered, datestamp) "
                                                        f"VALUES('{spifinder_field}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                                        f"'{spifinder_entry}', 'confirmed', 'automatic', 1, "
                                                        f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                elif species == 'stec':
                    if scheme == 'stec_serotype':
                        serotypedict = {}
                        serotypedict['O_antigen'] = sample_output_dict['serotype'].split(':')[0]
                        serotypedict['H_antigen'] = sample_output_dict['serotype'].split(':')[1]
                        for antigen, antigen_allele in serotypedict.items():
                            if antigen_allele != '-':
                                cur_seqdef.execute(
                                    f"SELECT allele_id FROM sequences WHERE allele_id = '{antigen_allele}' and locus = '{antigen}'")
                                present = cur_seqdef.fetchall()
                                if present == []:
                                    cur_seqdef.execute(
                                        f"SELECT sequence FROM sequences WHERE locus  ='{antigen}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
                                    longest_dummy_sequence = cur_seqdef.fetchall()
                                    if longest_dummy_sequence == []:
                                        dummysequence = 'TAG'
                                    else:
                                        dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
                                    cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                                                               VALUES('{antigen}','{antigen_allele}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                            f"allele_id, status, method, sender, "
                                            f"curator, date_entered, datestamp) "
                                            f"VALUES('{antigen}', (SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'), "
                                            f"'{antigen_allele}', 'confirmed', 'automatic', 1, "
                                            f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
            else:
                continue
        
        cur_isolates.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}'),(SELECT NOW()::TIMESTAMP), 'Typing results inserted', 1)")
        logging.info('Typing results insertion succesful')