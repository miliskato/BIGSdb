import logging
import re

import psycopg2
import requests

from .json_superclass import JsonSuperClass


class JsonTypingResultsInserter(JsonSuperClass):
    """
    Class containing definitions to insert typing results from json input
    """

    def __init__(self, isolatename: str, species: str, cur_isolates: psycopg2.extensions.cursor, cur_seqdef: psycopg2.extensions.cursor, sample_output_dict: dict) -> None:
        """
        :param isolatename: 
        :param species: commonly used bioit species name: either genus or specific like stec
        :param cur_isolates: isolate database connection object
        :param cur_seqdef: sequence definition database connection object
        :param sample_output_dict: results of sample
        """
        JsonSuperClass.__init__(self, isolatename, species, cur_isolates, cur_seqdef, sample_output_dict)

    def insert_typing_results(self, schemedict: dict) -> None:
        """
        Inserts typing results into bigsdb from json
        :param schemedict: dictionary of species specific schemes and their properties (found in config)
        :return: None
        """
        locuslist = []
        # Locuslist serves as to not insert duplicates (creates error in sql),
        # for Listeria e.g. prs and prfA are included in two schemes
        for scheme in schemedict:
            if scheme in self.sample_output_dict.keys():
                if schemedict[scheme]['type'] == 'regular':
                    for locus in self.sample_output_dict[scheme]['loci']:
                        if locus['Locus'] not in locuslist:
                            if locus['% Identity'] == '100.00' and locus['HSP/Locus length'] != '-' and eval(locus['HSP/Locus length']) == 1.0 and locus['Allele'] != 0 and locus['Allele'] != '?':
                                self._insert_allele_designation(locus['Locus'].replace("'", ""), locus['Allele'])
                                locuslist.append(locus['Locus'])
                            # the elif below is specific to Listeria pcr serogroup where 0's are included in the profiles
                            # (absent loci are required to define profiles)
                            # Bigsdb creates a null allele itself in the seqdef database
                            elif ((scheme == 'pcr_serogroup' or (scheme == 'bast' and locus['Locus'] == 'NadA_peptide')) \
                                    and locus['% Identity'] == '-' and locus['HSP/Locus length'] == '-') or scheme == 'cgmlst':
                                # in cgmlst you can have perfect multihits (?) that are then also considered as a zero in the custom profile by Benoit, thats why its outside of the ( )
                                self._insert_allele_designation(locus['Locus'], 0)
                                locuslist.append(locus['Locus'])

                elif schemedict[scheme]['type'] == 'irregular':
                    if scheme == 'pointfinder':
                        if self.sample_output_dict[scheme]['results'] != '[]':
                            eavhtmltable = '<table class="data"><tr><th>Hit</th><th>Antibiotic</th></tr>'
                            for result in self.sample_output_dict[scheme]['results']:
                                if result['Resistance'] != "Unknown":
                                    # Seeing as the allele db of pointfinder is empty at the beginning because the db is too hard to understand, we gradually add alleles.
                                    # sometimes a mutation will give resistance to more than 1 AB
                                    antibiotics = result['Resistance'].split(',')
                                    for antibiotic in antibiotics:
                                        antibiotic_reformatted = '_'.join(
                                            ['POINTFINDER', re.sub('-| ', '_', antibiotic).upper()])
                                        mutation = re.sub('[.]| ', '_', result['Mutation'])
                                        eavhtmltable = eavhtmltable + ''.join(
                                            [f'<tr><td><a href="/galaxyreports/{self.species}/', self.isolatename,
                                             '/report.html#',
                                             schemedict[scheme]['schemename_html'], '" target="_blank">',
                                             result['Mutation'], '</a></td>'])
                                        eavhtmltable = eavhtmltable + ''.join(['<td>', antibiotic, '</td></tr>'])
                                        self._insert_dummy_sequence_if_needed(antibiotic_reformatted, mutation)
                                        self._insert_allele_designation(antibiotic_reformatted, mutation)
                            eavhtmltable = eavhtmltable + '</table>'
                            self._insert_metadata('pointfinder_hits', eavhtmltable)
                    if self.species == 'mycobacterium':
                        if scheme == 'spoligotyping':
                            x = 1
                            for allele_id in list(self.sample_output_dict[scheme]['spoligotype_binary']):
                                locus = ''.join(['Spacer', str(x).zfill(2)])
                                x += 1
                                self._insert_allele_designation(locus, allele_id)
                            self._insert_metadata('spoligotype_binary', self.sample_output_dict[scheme]['spoligotype_binary'])
                            self._insert_metadata('spoligotype_octal', self.sample_output_dict[scheme]['spoligotype_octal'])
                        elif scheme == 'csb_rd':
                            for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                                locus = record.rstrip('_detected')  # need to be careful with rstrip and strip but in this case no issue
                                if self.sample_output_dict[scheme][record] is False:
                                    allele_id = 0
                                elif self.sample_output_dict[scheme][record] is True:
                                    allele_id = 1
                                self._insert_allele_designation(locus, allele_id)
                        elif scheme == 'amr_who':
                            # make a dict with field and tsv names to be able to insert
                            self.cur_isolates.execute(f"SELECT field FROM eav_fields WHERE category='AMR detection'")
                            fields = self.cur_isolates.fetchall()
                            amr_metadata_fields_tsv = {}
                            for field in fields:
                                if field[0].startswith('amr'):
                                    amr_metadata_fields_tsv[field[0]] = field[0]
                                else:
                                    amr_metadata_fields_tsv[field[0]] = ''.join(['amr_pheno_', field[0].split('_')[-1]])
                            for bigsdbname, jsonname in amr_metadata_fields_tsv.items():
                                self._insert_metadata(bigsdbname, self.sample_output_dict[scheme][jsonname])
                            # AMR results
                            self.cur_isolates.execute(
                                f"SELECT locus FROM scheme_members WHERE scheme_id = (SELECT id FROM schemes WHERE name = 'AMR_detection_WHO')")
                            loci = self.cur_isolates.fetchall()
                            for locus in loci:
                                jsonname = '_'.join(['amr_mutations', str(locus[0]).replace('_int', '_(int.)')])
                                if self.sample_output_dict[scheme][jsonname] != '-':
                                    for variant in self.sample_output_dict[scheme][jsonname].split(', '):
                                        variantreformatted = re.sub('[(]|[)]', '_', variant)
                                        # Bert explained that if the change is found in promotor, then it can change signs
                                        # And also honestly the db is really discrepant, e.g. how likely is this:
                                        # Rv1979c AA G_107_A Rv1979c_AA_G_107_A Uncertain significance CFZ CFZ_Uncertain_significance
                                        # Rv1979c PROM g_-107_a Rv1979c_PROM_g_-107_a Uncertain significance CFZ CFZ_Uncertain_significance
                                        # + there are really just duplicates in the db so I limit to 1, then its always the same.
                                        # Sometimes not only the sign changes when its in a promotor, but also the location, easiest solution is just to insert after it is found. Because sequences need to be unique for a locus, I take the longest sequence and add TAG
                                        self._insert_dummy_sequence_if_needed(locus[0], variantreformatted)
                                        sqlquery = """SELECT allele_id FROM sequences WHERE allele_id=%s AND locus = %s LIMIT 1;"""
                                        self.cur_seqdef.execute(sqlquery, (variantreformatted, locus[0]))
                                        allele_id = self.cur_seqdef.fetchall()[0][0]
                                        # Select From without * returns non-empty list like [(), (), (), ()] and is less compute intensive probably
                                        sqlquery = """
                                                   SELECT FROM allele_designations WHERE locus=%s AND 
                                                   isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate=%s) AND 
                                                   allele_id=%s;"""
                                        self.cur_isolates.execute(sqlquery, (locus[0], self.isolatename, allele_id))
                                        allele_designation_presence = self.cur_isolates.fetchall()
                                        if allele_designation_presence == []:
                                            self._insert_allele_designation(locus[0], allele_id)
                        elif scheme == 'hsp65':
                            if self.sample_output_dict[scheme]['loci'] != '[]':
                                for locus in self.sample_output_dict[scheme]['loci']:
                                    hit = '_'.join(['hsp65', re.sub('[.]| ', '_', locus['Species'])])
                                    sqlquery = """
                                               SELECT FROM eav_boolean WHERE isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s)
                                               AND field=%s;"""
                                    self.cur_isolates.execute(sqlquery, (self.isolatename, hit))
                                    presence_hsp65 = self.cur_isolates.fetchall()
                                    if presence_hsp65 == []:
                                        self._insert_metadata_bool(hit, 't')
                        elif scheme == 'ncbi_16s':
                            # ncbi 16s contains duplicate species
                            # looks like this in json: [{"DB_cluster": "Cluster_24", "Locus": "NR_114860.1", "% Identity": "95.50", "HSP/Locus length": "999/1077", "Contig": "NODE_353_length_1859_cov_4.154734", "Position in contig": "862..1859", "Species": "Mycobacterium peregrinum strain ATCC 14467 16S ribosomal RNA gene, partial sequence", "Accession": "NR_114860.1"}]
                            speciesandstrainhits = []
                            if self.sample_output_dict[scheme]['loci'] != '[]':
                                for hit in self.sample_output_dict[scheme]['loci']:
                                    speciesname = '_'.join([hit['Species'].split(' ')[0], hit['Species'].split(' ')[1]])
                                    if speciesname not in speciesandstrainhits:
                                        speciesandstrainhits.append(speciesname)
                                    strainname = '_'.join(
                                        [hit['Species'].split(' ')[0], hit['Species'].split(' ')[1], hit['Species'].split(' ')[2],
                                         hit['Species'].split(' ')[3]])
                                    if strainname not in speciesandstrainhits:
                                        speciesandstrainhits.append(strainname)
                            for hit in speciesandstrainhits:
                                hit_formatted = '_'.join(['ncbi16s', hit])
                                # check whether already exists in eav
                                sqlquery = """SELECT count(*) FROM eav_fields WHERE category='NCBI 16S' AND field=%s;"""
                                self.cur_isolates.execute(sqlquery, (hit_formatted,))
                                eav_exists = self.cur_isolates.fetchall()
                                if eav_exists[0][0] == 0:
                                    sqlquery = """
                                               INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) 
                                               VALUES(%s, 'boolean', 'NCBI 16S', '', 't', 't', (SELECT CURRENT_DATE), 1);"""
                                    self.cur_isolates.execute(sqlquery, (hit_formatted,))
                                self._insert_metadata_bool(hit_formatted, 't')
                    elif self.species == 'neisseria':
                        if scheme == 'resistance_genes':
                            for locus in self.sample_output_dict[scheme]['loci']:
                                if locus['Locus'] in ['penA', 'rpoB'] and locus['% Identity'] == '100.00' and locus['HSP/Locus length'] != '-' and eval(locus['HSP/Locus length']) == 1.0:
                                    response = requests.get(
                                        f"https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/loci/{locus['Locus']}/alleles/{locus['Allele']}")
                                    json_data = response.json()
                                    if json_data['status'] != '404' and json_data.get('linked_data') and 'PubMLST isolates' in json_data['linked_data']:
                                        for antibiotic in ['rifampicin_SIR', 'penicillin_SIR']:
                                            if antibiotic in json_data['linked_data']['PubMLST isolates'].keys():
                                                for record in json_data['linked_data']['PubMLST isolates'][antibiotic]:
                                                    if record['value'] == 'S':
                                                        self._insert_metadata('_'.join([antibiotic, 'S', 'frequency']), record['frequency'])
                                                    elif record['value'] == 'R':
                                                        self._insert_metadata('_'.join([antibiotic, 'R', 'frequency']), record['frequency'])
                    elif self.species == 'stec':
                        if scheme == 'serotype':
                            serotypedict = {}
                            serotypedict['O_antigen'] = self.sample_output_dict[scheme]['serotype'].split(':')[0]
                            serotypedict['H_antigen'] = self.sample_output_dict[scheme]['serotype'].split(':')[1]
                            for antigen, antigen_allele in serotypedict.items():
                                if antigen_allele != '-':
                                    self._insert_dummy_sequence_if_needed(antigen, antigen_allele)
                                    self._insert_allele_designation(antigen, antigen_allele)
                    elif self.species == 'salmonella':
                        if scheme == 'genotyphi':
                            self.cur_isolates.execute(f"SELECT field FROM eav_fields WHERE field like 'genotyphi%'")
                            genotyphi_susc_list = self.cur_isolates.fetchall()
                            for item in genotyphi_susc_list:
                                if item[0] in self.sample_output_dict[scheme]['results'] and self.sample_output_dict[scheme]['results'][item[0]] is not None:
                                    susceptibility = self.sample_output_dict[scheme]['results'][item[0]]
                                    self._insert_metadata(item[0], susceptibility)
                                    # insert new alleles
                                    variant = item[0].replace('susceptibility', 'variants')
                                    gene = item[0].replace('susceptibility', 'genes')
                                    genotyphi_field = item[0].replace('_susceptibility', '').upper()
                                    # get the genes and variants
                                    future_alleles = self.sample_output_dict[scheme]['results'][variant].split(';') + self.sample_output_dict[scheme]['results'][gene].split(';')
                                    for value in future_alleles:
                                        if value != '-':
                                            self._insert_dummy_sequence_if_needed(genotyphi_field, value)
                                            self._insert_allele_designation(genotyphi_field, value)
                        elif scheme == 'sistr' or scheme.startswith('seqsero2'):
                            if scheme == 'sistr':
                                serotyping_insert = self.sample_output_dict[scheme]['serotype_antigenic_formula']
                                if serotyping_insert != '-':
                                    self._salmonella_insert_antigens_into_db(serotyping_insert, scheme)
                                    self._insert_metadata(f'{scheme}_formula', serotyping_insert)
                                serotyping_insert = self.sample_output_dict[scheme]['serotype_concensus']
                                if serotyping_insert != '-':
                                    self._insert_metadata(f'{scheme}_serotype', serotyping_insert)
                            else:
                                serotyping_insert = self.sample_output_dict[scheme][f'{scheme}_Predicted_antigenic_profile']
                                self._salmonella_insert_antigens_into_db(serotyping_insert, scheme)
                                if serotyping_insert != '-:-:-':
                                    self._insert_metadata(f'{scheme}_formula', serotyping_insert)
                                serotyping_insert = self.sample_output_dict[scheme][f'{scheme}_Predicted_serotype']
                                if serotyping_insert != '- -:-:-':
                                    self._insert_metadata(f'{scheme}_serotype', serotyping_insert)
                        elif scheme.startswith('spifinder'):
                            hits = self.sample_output_dict[scheme]['results']
                            if hits != '[]':
                                inserted_alleledesignations_list = []
                                for SPI in hits:
                                    spifinder_entry = f"CatFunc{SPI['category_function']}__{SPI['accession']}"
                                    spifinder_field = f"{scheme}_{SPI['SPI']}".upper()
                                    if spifinder_entry not in inserted_alleledesignations_list:
                                        self._insert_dummy_sequence_if_needed(spifinder_field, spifinder_entry)
                                        self._insert_allele_designation(spifinder_field, spifinder_entry)
                                        inserted_alleledesignations_list.append(spifinder_entry)
            else:
                logging.warning(f"scheme {scheme} not present in json file")
        self._insert_history('Typing results inserted')
        logging.info('Typing results insertion succesful')

    def _salmonella_insert_antigens_into_db(self, raw_formula: str, scheme: str) -> None:
        """
        Inserts antigens separately from the formula
        :param raw_formula: serotype formula O:H1:H2
        :param scheme: schemename
        :return: None
        """
        antigensdict = {"O_antigen": raw_formula.split(':')[0].split(','),
                        "H1_antigen": raw_formula.split(':')[1].split(','),
                        "H2_antigen": raw_formula.split(':')[2].split(',')}
        antigens = ["O_antigen", "H1_antigen", "H2_antigen"]
        for antigen in antigens:
            field = f'{scheme}_{antigen}'.upper()
            entries = antigensdict[antigen]
            for entry in entries:
                if entry != '-':
                    self._insert_dummy_sequence_if_needed(field, entry)
                    self._insert_allele_designation(field, entry)
