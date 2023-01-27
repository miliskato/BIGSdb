import logging
import re
from typing import Any, Dict, List, Union

import psycopg2.extensions
import requests

from .json_superclass import JsonSuperClass
from .psql_tables_queries import TblAlleleDesignations, TblHistory, TblEavBoolean


class JsonTypingResultsInserter(JsonSuperClass):
    """
    Class containing definitions to insert typing results from json input
    """

    def __init__(self, isolatename: str, species: str,
                 sample_output_dict: Dict[str, Any], config_data: Dict[str, Any]) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param sample_output_dict: results of sample
        :param config_data: the bigsdb config data
        :return: None
        """
        JsonSuperClass.__init__(self, isolatename, species, sample_output_dict, config_data)
        self.schemedict: Dict[str, Dict[str, str]] = self._config_data['species_json'][self._species]['typing_schemes']

    def insert_typing_results(self) -> None:
        """
        Inserts typing results into bigsdb from json
        :return: None
        """
        with TblAlleleDesignations(self.species) as self.isolates_ad_psql_tbl:
            locusset = set()  # Locusset serves as to not insert duplicates (creates error in sql),
            # for Listeria e.g. prs and prfA are included in two schemes
            for scheme in self.schemedict:
                if scheme in self._sample_output_dict:
                    if self.schemedict[scheme]['type'] == 'regular':
                        for locus in self._sample_output_dict[scheme]['loci']:
                            if locus['Locus'] not in locusset:
                                if locus['% Identity'] == '100.00' and locus['HSP/Locus length'] != '-' and float(locus['HSP/Locus length']) == 1.0 and locus['Allele'] != 0 and locus['Allele'] != '?':
                                    self.isolates_ad_psql_tbl.insert_designation((locus['Locus'].replace("'", ""), self._isolatename, locus['Allele']))
                                    locusset.add(locus['Locus'])
                                # the elif below is specific to Listeria pcr serogroup where 0's are included in the profiles
                                # (absent loci are required to define profiles)
                                # Bigsdb creates a null allele itself in the seqdef database
                                elif ((scheme == 'pcr_serogroup' or (scheme == 'bast' and locus['Locus'] == 'NadA_peptide'))
                                        and locus['% Identity'] == '-' and locus['HSP/Locus length'] == '-') or scheme == 'cgmlst':
                                    # in cgmlst you can have perfect multihits (?) that are then also considered as a zero in the custom profile by Benoit, thats why its outside of the ( )
                                    self.isolates_ad_psql_tbl.insert_designation((locus['Locus'], self._isolatename, '0'))
                                    locusset.add(locus['Locus'])

                    elif self.schemedict[scheme]['type'] == 'irregular':
                        if scheme == 'pointfinder':
                            if len(self._sample_output_dict[scheme]['results']) != 0:
                                eavhtmltable = '<table class="data"><tr><th>Hit</th><th>Antibiotic</th></tr>'
                                for result in self._sample_output_dict[scheme]['results']:
                                    if result['Resistance'] != "Unknown":
                                        # Seeing as the allele db of pointfinder is empty at the beginning because the db is too hard to understand, we gradually add alleles.
                                        # sometimes a mutation will give resistance to more than 1 AB
                                        antibiotics: List[str] = result['Resistance'].split(',')
                                        for antibiotic in antibiotics:
                                            antibiotic_reformatted: str = '_'.join(
                                                ['POINTFINDER', re.sub('-| ', '_', antibiotic).upper()])
                                            mutation: str = re.sub('[.]| ', '_', result['Mutation'])
                                            eavhtmltable = eavhtmltable + ''.join(
                                                [f'<tr><td><a href="/galaxyreports/{self._species}/', self._isolatename,
                                                 '/report.html#',
                                                 self.schemedict[scheme]['schemename_html'], '" target="_blank">',
                                                 result['Mutation'], '</a></td>'])
                                            eavhtmltable = eavhtmltable + ''.join(['<td>', antibiotic, '</td></tr>'])
                                            self._insert_dummy_sequence_if_needed(antibiotic_reformatted, mutation)
                                            self.isolates_ad_psql_tbl.insert_designation((antibiotic_reformatted, self._isolatename, mutation))
                                eavhtmltable = eavhtmltable + '</table>'
                                self._insert_metadata('pointfinder_hits', eavhtmltable)
                        if self._species == 'mycobacterium':
                            if scheme == 'spoligotyping':
                                for index, allele_id in enumerate(self._sample_output_dict[scheme]['spoligotype_binary']):
                                    locus: str = ''.join(['Spacer', str(index + 1).zfill(2)])
                                    self.isolates_ad_psql_tbl.insert_designation((locus, self._isolatename, str(allele_id)))
                                self._insert_metadata('spoligotype_binary', self._sample_output_dict[scheme]['spoligotype_binary'])
                                self._insert_metadata('spoligotype_octal', self._sample_output_dict[scheme]['spoligotype_octal'])
                            elif scheme == 'csb_rd':
                                for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                                    locus: str = record.rstrip('_detected')  # need to be careful with rstrip and strip but in this case no issue
                                    allele_id: int = 1 if self._sample_output_dict[scheme][record] else 0
                                    self.isolates_ad_psql_tbl.insert_designation((locus, self._isolatename, str(allele_id)))
                            elif scheme == 'amr_who':
                                # make a dict with field and tsv names to be able to insert
                                self.isolates_psql_db.execute_query("SELECT field FROM eav_fields WHERE category='AMR detection'")
                                fields = self.isolates_psql_db.fetchall()
                                amr_metadata_fields_tsv: Dict = {}
                                for field in fields:
                                    if field[0].startswith('amr'):
                                        amr_metadata_fields_tsv[field[0]] = field[0]
                                    else:
                                        amr_metadata_fields_tsv[field[0]] = ''.join(['amr_pheno_', field[0].split('_')[-1]])
                                for bigsdbname, jsonname in amr_metadata_fields_tsv.items():
                                    self._insert_metadata(bigsdbname, self._sample_output_dict[scheme][jsonname])
                                # AMR results
                                self.isolates_psql_db.execute_query(
                                    "SELECT locus FROM scheme_members WHERE scheme_id = (SELECT id FROM schemes WHERE name = 'AMR_detection_WHO')")
                                for locus in self.isolates_psql_db.fetchall():
                                    jsonname: str = '_'.join(['amr_mutations', str(locus[0]).replace('_int', '_(int.)')])
                                    if self._sample_output_dict[scheme][jsonname] != '-':
                                        variantsset = set()
                                        for variant in self._sample_output_dict[scheme][jsonname].split(', '):
                                            variantreformatted: str = re.sub('[(]|[)]', '_', variant)
                                            # Bert explained that if the change is found in promotor, then it can change signs
                                            # And also honestly the db is really discrepant, e.g. how likely is this:
                                            # Rv1979c AA G_107_A Rv1979c_AA_G_107_A Uncertain significance CFZ CFZ_Uncertain_significance
                                            # Rv1979c PROM g_-107_a Rv1979c_PROM_g_-107_a Uncertain significance CFZ CFZ_Uncertain_significance
                                            # + there are really just duplicates in the db so I limit to 1, then it's always the same.
                                            # Sometimes not only the sign changes when its in a promotor, but also the location,
                                            # easiest solution is just to insert after it is found.
                                            self._insert_dummy_sequence_if_needed(locus[0], variantreformatted)
                                            if variantreformatted not in variantsset:
                                                self.isolates_ad_psql_tbl.insert_designation((locus[0], self._isolatename, variantreformatted))
                                                variantsset.add(variantreformatted)
                            elif scheme == 'hsp65':
                                if len(self._sample_output_dict[scheme]['loci']) != 0:
                                    speciesset = set()
                                    with TblEavBoolean(self._species) as isolates_eavb_psql_tbl:
                                        for locus in self._sample_output_dict[scheme]['loci']:
                                            hit: str = '_'.join(['hsp65', re.sub('[.]| ', '_', locus['Species'])])
                                            if hit not in speciesset:
                                                isolates_eavb_psql_tbl.insert_eav_isolate((self._isolatename, hit, 't'))
                                                speciesset.add(hit)
                            elif scheme == 'ncbi_16s':
                                # ncbi 16s contains duplicate species
                                """
                                looks like this in json: 
                                [{"DB_cluster": "Cluster_24", "Locus": "NR_114860.1", "% Identity": "95.50", 
                                  "HSP/Locus length": "999/1077", "Contig": "NODE_353_length_1859_cov_4.154734", 
                                  "Position in contig": "862..1859", 
                                  "Species": "Mycobacterium peregrinum strain ATCC 14467 16S ribosomal RNA gene, partial sequence", 
                                  "Accession": "NR_114860.1"}]
                                """
                                speciesandstrainhits = set()
                                if len(self._sample_output_dict[scheme]['loci']) != 0:
                                    for hit in self._sample_output_dict[scheme]['loci']:
                                        speciesname: str = '_'.join([hit['Species'].split(' ')[0], hit['Species'].split(' ')[1]])
                                        if speciesname not in speciesandstrainhits:
                                            speciesandstrainhits.add(speciesname)
                                        strainname: str = '_'.join(
                                            [hit['Species'].split(' ')[0], hit['Species'].split(' ')[1], hit['Species'].split(' ')[2],
                                             hit['Species'].split(' ')[3]])
                                        if strainname not in speciesandstrainhits:
                                            speciesandstrainhits.add(strainname)
                                with TblEavBoolean(self._species) as isolates_eavb_psql_tbl:
                                    for hit in speciesandstrainhits:
                                        hit_formatted: str = '_'.join(['ncbi16s', hit])
                                        # check whether already exists in eav
                                        sqlquery = """SELECT count(*) FROM eav_fields WHERE category='NCBI 16S' AND field=%s;"""
                                        self.isolates_psql_db.execute_query(sqlquery, (hit_formatted,))
                                        eav_exists = self.isolates_psql_db.fetchall()
                                        if eav_exists[0][0] == 0:
                                            sqlquery = """
                                                       INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) 
                                                       VALUES(%s, 'boolean', 'NCBI 16S', '', 't', 't', (SELECT CURRENT_DATE), 1);"""
                                            self.isolates_psql_db.execute_query(sqlquery, (hit_formatted,))
                                        isolates_eavb_psql_tbl.insert_eav_isolate((self._isolatename, hit_formatted, 't'))
                        elif self._species == 'neisseria':
                            if scheme == 'resistance_genes' and len(self._sample_output_dict[scheme]['loci']) != 0:
                                for locus in self._sample_output_dict[scheme]['loci']:
                                    if locus['Locus'] in ['penA', 'rpoB'] and locus['% Identity'] == '100.00' and locus['HSP/Locus length'] != '-' and float(locus['HSP/Locus length']) == 1.0:
                                        response: requests.models.Response = requests.get(
                                            f"https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/loci/{locus['Locus']}/alleles/{locus['Allele']}")
                                        json_data: Dict = response.json()
                                        if json_data['status'] != '404' and json_data.get('linked_data') and 'PubMLST isolates' in json_data['linked_data']:
                                            for antibiotic in ['rifampicin_SIR', 'penicillin_SIR']:
                                                if antibiotic in json_data['linked_data']['PubMLST isolates']:
                                                    for record in json_data['linked_data']['PubMLST isolates'][antibiotic]:
                                                        self._insert_metadata('_'.join([antibiotic, record['value'], 'frequency']),
                                                                              record['frequency'])
                        elif self._species == 'stec':
                            if scheme == 'serotype':
                                serotypedict = {'O_antigen': self._sample_output_dict[scheme]['serotype'].split(':')[0],
                                                'H_antigen': self._sample_output_dict[scheme]['serotype'].split(':')[1]}
                                for antigen, antigen_allele in serotypedict.items():
                                    if antigen_allele != '-':
                                        self._insert_dummy_sequence_if_needed(antigen, antigen_allele)
                                        self.isolates_ad_psql_tbl.insert_designation((antigen, self._isolatename, antigen_allele))
                        elif self._species == 'salmonella':
                            if scheme == 'genotyphi':
                                self.isolates_psql_db.execute_query("SELECT field FROM eav_fields WHERE field like 'genotyphi%susceptibility'")
                                for item in self.isolates_psql_db.fetchall():
                                    if item[0] in self._sample_output_dict[scheme]['results'] and self._sample_output_dict[scheme]['results'][item[0]] is not None:
                                        susceptibility: str = self._sample_output_dict[scheme]['results'][item[0]]
                                        self._insert_metadata(item[0], susceptibility)
                                        # insert new alleles
                                        variant = item[0].replace('susceptibility', 'variants')
                                        gene = item[0].replace('susceptibility', 'genes')
                                        genotyphi_field = item[0].replace('_susceptibility', '').upper()
                                        # get the genes and variants
                                        future_alleles = self._sample_output_dict[scheme]['results'][variant].split(';') + self._sample_output_dict[scheme]['results'][gene].split(';')
                                        for value in future_alleles:
                                            if value != '-':
                                                self._insert_dummy_sequence_if_needed(genotyphi_field, value)
                                                self.isolates_ad_psql_tbl.insert_designation((genotyphi_field, self._isolatename, value))
                            elif scheme == 'sistr':
                                serotyping_insert = self._sample_output_dict[scheme]['serotype_antigenic_formula']
                                if serotyping_insert != '-':
                                    self._salmonella_insert_antigens_into_db(serotyping_insert, scheme)
                                    self._insert_metadata(f'{scheme}_formula', serotyping_insert)
                                serotyping_insert = self._sample_output_dict[scheme]['serotype_concensus']
                                if serotyping_insert != '-':
                                    self._insert_metadata(f'{scheme}_serotype', serotyping_insert)
                            elif scheme.startswith('seqsero2'):
                                serotyping_insert = self._sample_output_dict[scheme][f'{scheme}_Predicted_antigenic_profile']
                                self._salmonella_insert_antigens_into_db(serotyping_insert, scheme)
                                if serotyping_insert != '-:-:-':
                                    self._insert_metadata(f'{scheme}_formula', serotyping_insert)
                                serotyping_insert = self._sample_output_dict[scheme][f'{scheme}_Predicted_serotype']
                                if serotyping_insert != '- -:-:-':
                                    self._insert_metadata(f'{scheme}_serotype', serotyping_insert)
                            elif scheme.startswith('spifinder'):
                                hits: List = self._sample_output_dict[scheme]['results']
                                if len(hits) != 0:
                                    inserted_alleledesignations_list = set()
                                    for spi in hits:
                                        spifinder_entry: str = f"CatFunc{spi['category_function']}__{spi['accession']}"
                                        spifinder_field: str = f"{scheme}_{spi['SPI']}".upper()
                                        if spifinder_entry not in inserted_alleledesignations_list:
                                            self._insert_dummy_sequence_if_needed(spifinder_field, spifinder_entry)
                                            self.isolates_ad_psql_tbl.insert_designation((spifinder_field, self._isolatename, spifinder_entry))
                                            inserted_alleledesignations_list.add(spifinder_entry)
                else:
                    logging.warning(f"scheme {scheme} not present in json file")
            with TblHistory(self._species) as isolates_history_psql_tbl:
                isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Typing results inserted'))
            logging.info('Typing results insertion succesful')

    def _salmonella_insert_antigens_into_db(self, raw_formula: str, scheme: str) -> None:
        """
        Inserts antigens separately from the formula
        :param raw_formula: serotype formula O:H1:H2
        :param scheme: schemename
        :return: None
        """
        raw_formula_splitted: List = raw_formula.split(':')
        antigensdict = {"O_antigen": raw_formula_splitted[0].split(','),
                        "H1_antigen": raw_formula_splitted[1].split(','),
                        "H2_antigen": raw_formula_splitted[2].split(',')}
        antigens = ["O_antigen", "H1_antigen", "H2_antigen"]
        for antigen in antigens:
            field = f'{scheme}_{antigen}'.upper()
            entries = antigensdict[antigen]
            for entry in entries:
                if entry != '-':
                    self._insert_dummy_sequence_if_needed(field, entry)
                    self.isolates_ad_psql_tbl.insert_designation((field, self._isolatename, entry))
