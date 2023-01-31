import logging
import re
from typing import Any, Dict, List, Union

import psycopg2.extensions
import requests

from .json_superclass import JsonSuperClass
from .psql_tables_queries import TblAlleleDesignations, TblHistory, TblEavBoolean, TblEavText, TblEavFields, TblSchemeMembers


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
        self._schemedict: Dict[str, Dict[str, str]] = self._config_data['species_json'][self._species]['typing_schemes']
        self._scheme = None

    def insert_typing_results(self) -> None:
        """
        Inserts typing results into bigsdb from json
        :return: None
        """
        with TblAlleleDesignations(self._species) as self._isolates_ad_psql_tbl, TblEavText(self._species) as self._isolates_eavt_psql_tbl:
            for scheme in self._schemedict:
                if scheme in self._sample_output_dict:
                    self._scheme = scheme
                    if self._schemedict[self._scheme]['type'] == 'regular':
                        self._process_regular_typing_scheme()
                    elif self._schemedict[self._scheme]['type'] == 'irregular':
                        self._process_irregular_typing_scheme()
                else:
                    logging.warning(f"scheme {self._scheme} not present in json file")
            with TblHistory(self._species) as isolates_history_psql_tbl:
                isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Typing results inserted'))
            logging.info('Typing results insertion succesful')

    def _process_regular_typing_scheme(self) -> None:
        """
        Processes regular typing scheme results
        :return: None
        """
        locusset = set()  # Locusset serves as to not insert duplicates (creates error in sql),
        # for Listeria e.g. prs and prfA are included in two self._schemes
        for locus in self._sample_output_dict[self._scheme]['loci']:
            if locus['Locus'] not in locusset:
                if locus['% Identity'] == '100.00' and locus['HSP/Locus length'] != '-' and float(
                        locus['HSP/Locus length']) == 1.0 and locus['Allele'] != 0 and locus['Allele'] != '?':
                    self._isolates_ad_psql_tbl.insert_designation(
                        (locus['Locus'].replace("'", ""), self._isolatename, locus['Allele']))
                    locusset.add(locus['Locus'])
                # the elif below is specific to Listeria pcr serogroup where 0's are included in the profiles
                # (absent loci are required to define profiles)
                # Bigsdb creates a null allele itself in the seqdef database
                elif ((self._scheme == 'pcr_serogroup' or (self._scheme == 'bast' and locus['Locus'] == 'NadA_peptide'))
                      and locus['% Identity'] == '-' and locus['HSP/Locus length'] == '-') or self._scheme == 'cgmlst':
                    # in cgmlst you can have perfect multihits (?) that are then also considered as a zero in the custom profile by Benoit, thats why its outside of the ( )
                    self._isolates_ad_psql_tbl.insert_designation((locus['Locus'], self._isolatename, '0'))
                    locusset.add(locus['Locus'])
                    
    def _process_irregular_typing_scheme(self) -> None:
        if self._scheme == 'pointfinder':
            self.__process_irregular_typing_scheme_pointfinder()
        if self._species == 'mycobacterium':
            self.__process_irregular_typing_scheme_mycobacterium_specific()
        elif self._species == 'neisseria':
            self.__process_irregular_typing_scheme_neisseria_specific()
        elif self._species == 'stec':
            self.__process_irregular_typing_scheme_stec_specific()
        elif self._species == 'salmonella':
            self.__process_irregular_typing_scheme_salmonella_specific()
    
    def __process_irregular_typing_scheme_pointfinder(self) -> None:
        """
        Processes and inserts pointfinder results (available in multiple species)
        :return: None
        """
        if len(self._sample_output_dict[self._scheme]['results']) != 0:
            eavhtmltable = '<table class="data"><tr><th>Hit</th><th>Antibiotic</th></tr>'
            for result in self._sample_output_dict[self._scheme]['results']:
                if result['Resistance'] != "Unknown":
                    # Seeing as the allele db of pointfinder is empty at the beginning because the db is too hard to understand, we gradually add alleles.
                    # sometimes a mutation will give resistance to more than 1 AB
                    antibiotics: List[str] = result['Resistance'].split(',')
                    for antibiotic in antibiotics:
                        antibiotic_reformatted = '_'.join(
                            ['POINTFINDER', re.sub('-| ', '_', antibiotic).upper()])
                        mutation = re.sub('[.]| ', '_', result['Mutation'])
                        eavhtmltable = eavhtmltable + ''.join(
                            [f'<tr><td><a href="/galaxyreports/{self._species}/', self._isolatename,
                             '/report.html#',
                             self._schemedict[self._scheme]['schemename_html'], '" target="_blank">',
                             result['Mutation'], '</a></td>'])
                        eavhtmltable = eavhtmltable + ''.join(['<td>', antibiotic, '</td></tr>'])
                        self._insert_dummy_sequence_if_needed(antibiotic_reformatted, mutation)
                        self._isolates_ad_psql_tbl.insert_designation(
                            (antibiotic_reformatted, self._isolatename, mutation))
            eavhtmltable = eavhtmltable + '</table>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'pointfinder_hits', eavhtmltable))
            
    def __process_irregular_typing_scheme_mycobacterium_specific(self) -> None:
        """
        Processes and inserts mycobacterium results
        :return: None
        """
        if self._scheme == 'spoligotyping':
            for index, allele_id in enumerate(self._sample_output_dict[self._scheme]['spoligotype_binary']):
                locus = ''.join(['Spacer', str(index + 1).zfill(2)])
                self._isolates_ad_psql_tbl.insert_designation((locus, self._isolatename, str(allele_id)))
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'spoligotype_binary',
                                                             self._sample_output_dict[self._scheme][
                                                                 'spoligotype_binary']))
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'spoligotype_octal',
                                                             self._sample_output_dict[self._scheme][
                                                                 'spoligotype_octal']))
        elif self._scheme == 'csb_rd':
            for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                locus = record.rstrip(
                    '_detected')  # need to be careful with rstrip and strip but in this case no issue
                allele_id = '1' if self._sample_output_dict[self._scheme][record] else '0'
                self._isolates_ad_psql_tbl.insert_designation((locus, self._isolatename, allele_id))
        elif self._scheme == 'amr_who':
            # make a dict with field and tsv names to be able to insert
            with TblEavFields(self._species) as isolates_eavf_psql_tbl:
                fields = isolates_eavf_psql_tbl.select_fields_amr()
            amr_metadata_fields_tsv: Dict = {}
            for field in fields:
                if field[0].startswith('amr'):
                    amr_metadata_fields_tsv[field[0]] = field[0]
                else:
                    amr_metadata_fields_tsv[field[0]] = ''.join(['amr_pheno_', field[0].split('_')[-1]])
            for bigsdbname, jsonname in amr_metadata_fields_tsv.items():
                self._isolates_eavt_psql_tbl.insert_eav_isolate(
                    (self._isolatename, bigsdbname, self._sample_output_dict[self._scheme][jsonname]))
            # AMR results
            with TblSchemeMembers(self._species, 'isolates') as isolates_schememembers_psql_tbl:
                amr_loci = isolates_schememembers_psql_tbl.select_loci_amr()
            for locus in amr_loci:
                jsonname = '_'.join(['amr_mutations', str(locus[0]).replace('_int', '_(int.)')])
                if self._sample_output_dict[self._scheme][jsonname] != '-':
                    variantsset = set()
                    for variant in self._sample_output_dict[self._scheme][jsonname].split(', '):
                        variantreformatted = re.sub('[(]|[)]', '_', variant)
                        # Bert explained that if the change is found in promotor, then it can change signs
                        # And also honestly the db is really discrepant, e.g. how likely is this:
                        # Rv1979c AA G_107_A Rv1979c_AA_G_107_A Uncertain significance CFZ CFZ_Uncertain_significance
                        # Rv1979c PROM g_-107_a Rv1979c_PROM_g_-107_a Uncertain significance CFZ CFZ_Uncertain_significance
                        # + there are really just duplicates in the db so I limit to 1, then it's always the same.
                        # Sometimes not only the sign changes when its in a promotor, but also the location,
                        # easiest solution is just to insert after it is found.
                        self._insert_dummy_sequence_if_needed(locus[0], variantreformatted)
                        if variantreformatted not in variantsset:
                            self._isolates_ad_psql_tbl.insert_designation(
                                (locus[0], self._isolatename, variantreformatted))
                            variantsset.add(variantreformatted)
        elif self._scheme == 'hsp65':
            if len(self._sample_output_dict[self._scheme]['loci']) != 0:
                speciesset = set()
                with TblEavBoolean(self._species) as isolates_eavb_psql_tbl:
                    for locus in self._sample_output_dict[self._scheme]['loci']:
                        hit = '_'.join(['hsp65', re.sub('[.]| ', '_', locus['Species'])])
                        if hit not in speciesset:
                            isolates_eavb_psql_tbl.insert_eav_isolate((self._isolatename, hit, 't'))
                            speciesset.add(hit)
        elif self._scheme == 'ncbi_16s':
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
            if len(self._sample_output_dict[self._scheme]['loci']) != 0:
                for hit in self._sample_output_dict[self._scheme]['loci']:
                    speciesname = '_'.join([hit['Species'].split(' ')[0], hit['Species'].split(' ')[1]])
                    if speciesname not in speciesandstrainhits:
                        speciesandstrainhits.add(speciesname)
                    strainname = '_'.join(
                        [hit['Species'].split(' ')[0], hit['Species'].split(' ')[1], hit['Species'].split(' ')[2],
                         hit['Species'].split(' ')[3]])
                    if strainname not in speciesandstrainhits:
                        speciesandstrainhits.add(strainname)
            with TblEavBoolean(self._species) as isolates_eavb_psql_tbl:
                for hit in speciesandstrainhits:
                    hit_formatted = '_'.join(['ncbi16s', hit])
                    # check whether already exists in eav
                    with TblEavFields(self._species) as isolates_eavf_psql_tbl:
                        eav_exists = isolates_eavf_psql_tbl.select_count_16s((hit_formatted,))
                        if eav_exists[0][0] == 0:
                            isolates_eavf_psql_tbl.insert_fields_16s((hit_formatted,))
                    isolates_eavb_psql_tbl.insert_eav_isolate((self._isolatename, hit_formatted, 't'))

    def __process_irregular_typing_scheme_neisseria_specific(self) -> None:
        """
        Processes and inserts neisseria results
        :return: None
        """
        if self._scheme == 'resistance_genes' and len(self._sample_output_dict[self._scheme]['loci']) != 0:
            for locus in self._sample_output_dict[self._scheme]['loci']:
                if locus['Locus'] in ['penA', 'rpoB'] and locus['% Identity'] == '100.00' and \
                        locus['HSP/Locus length'] != '-' and float(locus['HSP/Locus length']) == 1.0:
                    response: requests.models.Response = requests.get(
                        f"https://rest.pubmlst.org/db/pubmlst_neisseria_seqdef/loci/{locus['Locus']}/alleles/{locus['Allele']}")
                    json_data: Dict = response.json()
                    if json_data['status'] != '404' and json_data.get('linked_data') and 'PubMLST isolates' in \
                            json_data['linked_data']:
                        for antibiotic in ['rifampicin_SIR', 'penicillin_SIR']:
                            if antibiotic in json_data['linked_data']['PubMLST isolates']:
                                for record in json_data['linked_data']['PubMLST isolates'][antibiotic]:
                                    self._isolates_eavt_psql_tbl.insert_eav_isolate(
                                        (self._isolatename, '_'.join([antibiotic, record['value'], 'frequency']),
                                         record['frequency']))

    def __process_irregular_typing_scheme_stec_specific(self) -> None:
        """
        Processes and inserts stec results
        :return: None
        """
        if self._scheme == 'serotype':
            serotypedict = {'O_antigen': self._sample_output_dict[self._scheme]['serotype'].split(':')[0],
                            'H_antigen': self._sample_output_dict[self._scheme]['serotype'].split(':')[1]}
            for antigen, antigen_allele in serotypedict.items():
                if antigen_allele != '-':
                    self._insert_dummy_sequence_if_needed(antigen, antigen_allele)
                    self._isolates_ad_psql_tbl.insert_designation((antigen, self._isolatename, antigen_allele))
                    
    def __process_irregular_typing_scheme_salmonella_specific(self) -> None:
        """
        Processes and inserts Salmonella results
        :return: None
        """
        if self._scheme == 'genotyphi':
            with TblEavFields(self._species) as isolates_eavf_psql_tbl:
                fields_genotyphi = isolates_eavf_psql_tbl.select_fields_like(('genotyphi%susceptibility',))
            for item in fields_genotyphi:
                if item[0] in self._sample_output_dict[self._scheme]['results'] and \
                        self._sample_output_dict[self._scheme]['results'][item[0]] is not None:
                    susceptibility: str = self._sample_output_dict[self._scheme]['results'][item[0]]
                    self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, item[0], susceptibility))
                    # insert new alleles
                    variant = item[0].replace('susceptibility', 'variants')
                    gene = item[0].replace('susceptibility', 'genes')
                    genotyphi_field = item[0].replace('_susceptibility', '').upper()
                    # get the genes and variants
                    future_alleles = self._sample_output_dict[self._scheme]['results'][variant].split(';') + \
                                     self._sample_output_dict[self._scheme]['results'][gene].split(';')
                    for value in future_alleles:
                        if value != '-':
                            self._insert_dummy_sequence_if_needed(genotyphi_field, value)
                            self._isolates_ad_psql_tbl.insert_designation(
                                (genotyphi_field, self._isolatename, value))
        elif self._scheme == 'sistr':
            serotyping_insert = self._sample_output_dict[self._scheme]['serotype_antigenic_formula']
            if serotyping_insert != '-':
                self.___salmonella_insert_antigens_into_db(serotyping_insert)
                self._isolates_eavt_psql_tbl.insert_eav_isolate(
                    (self._isolatename, f'{self._scheme}_formula', serotyping_insert))
            serotyping_insert = self._sample_output_dict[self._scheme]['serotype_concensus']
            if serotyping_insert != '-':
                self._isolates_eavt_psql_tbl.insert_eav_isolate(
                    (self._isolatename, f'{self._scheme}_serotype', serotyping_insert))
        elif self._scheme.startswith('seqsero2'):
            serotyping_insert = self._sample_output_dict[self._scheme][
                f'{self._scheme}_Predicted_antigenic_profile']
            self.___salmonella_insert_antigens_into_db(serotyping_insert)
            if serotyping_insert != '-:-:-':
                self._isolates_eavt_psql_tbl.insert_eav_isolate(
                    (self._isolatename, f'{self._scheme}_formula', serotyping_insert))
            serotyping_insert = self._sample_output_dict[self._scheme][f'{self._scheme}_Predicted_serotype']
            if serotyping_insert != '- -:-:-':
                self._isolates_eavt_psql_tbl.insert_eav_isolate(
                    (self._isolatename, f'{self._scheme}_serotype', serotyping_insert))
        elif self._scheme.startswith('spifinder'):
            hits: List = self._sample_output_dict[self._scheme]['results']
            if len(hits) != 0:
                inserted_alleledesignations_list = set()
                for spi in hits:
                    spifinder_entry = f"CatFunc{spi['category_function']}__{spi['accession']}"
                    spifinder_field = f"{self._scheme}_{spi['SPI']}".upper()
                    if spifinder_entry not in inserted_alleledesignations_list:
                        self._insert_dummy_sequence_if_needed(spifinder_field, spifinder_entry)
                        self._isolates_ad_psql_tbl.insert_designation(
                            (spifinder_field, self._isolatename, spifinder_entry))
                        inserted_alleledesignations_list.add(spifinder_entry)
                        
    def ___salmonella_insert_antigens_into_db(self, raw_formula: str) -> None:
        """
        Inserts antigens separately from the formula
        :param raw_formula: serotype formula O:H1:H2
        :return: None
        """
        raw_formula_splitted: List = raw_formula.split(':')
        antigensdict = {"O_antigen": raw_formula_splitted[0].split(','),
                        "H1_antigen": raw_formula_splitted[1].split(','),
                        "H2_antigen": raw_formula_splitted[2].split(',')}
        antigens = ["O_antigen", "H1_antigen", "H2_antigen"]
        for antigen in antigens:
            field = f'{self._scheme}_{antigen}'.upper()
            entries = antigensdict[antigen]
            for entry in entries:
                if entry != '-':
                    self._insert_dummy_sequence_if_needed(field, entry)
                    self._isolates_ad_psql_tbl.insert_designation((field, self._isolatename, entry))
