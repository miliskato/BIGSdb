import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from .json_superclass import JsonSuperClass
from .psql import TblAlleleDesignations, TblEavBoolean, TblEavFields, TblEavFloat, TblEavText, TblHistory, TblIsolates, TblSchemeMembers
from ..utils.html_tbl_templates import HtmlMobSuiteTableBuilder
from ..utils.literal_helper import validate_literal
from ..utils.url_helper import UrlHelper

ModeLiteral = Literal['kmer', 'kmerread', 'allele']
ModeValue = Union[ModeLiteral, str]


class JsonTypingResultsInserter(JsonSuperClass):
    """
    Class containing definitions to insert typing results from json input
    """

    def __init__(self, isolatename: str, species: str,
                 json_report_dict: JsonReportDict, config_data: Dict[str, Any], report_access: str) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param json_report_dict: results of sample
        :param config_data: the bigsdb config data
        :param report_access: report dir from mongo
        :return: None
        """
        super().__init__(isolatename, species, json_report_dict, config_data)
        self._report_access = Path(report_access)
        self._schemedict: Dict[str, Dict[str, str]] = self._bigsdb_config_data['species_json'][self._species]['typing_schemes']
        self._scheme = None
        self._locusset = set()  # locusset serves as to not insert duplicates (creates error in sql),
        # for Listeria e.g. prs and prfA are included in two self._schemes

    def insert_typing_results(self) -> None:
        """
        Inserts typing results into bigsdb from json
        :return: None
        """
        with TblAlleleDesignations(self._species) as self._isolates_ad_psql_tbl, TblEavText(
                self._species) as self._isolates_eavt_psql_tbl:
            if self._schemedict is None:
                return
            for scheme in self._schemedict:
                self._scheme = scheme
                if self._scheme in self._json_report_dict:
                    if self._schemedict[self._scheme]['type'] == 'regular':
                        self._process_regular_typing_scheme()
                    elif self._schemedict[self._scheme]['type'] == 'irregular':
                        self._process_irregular_typing_scheme()
                elif self._scheme == 'rmlst_identification':
                    self._process_rmlst_identification()
                elif self._scheme == 'mob_suite_detection':
                    self._process_mob_suite()
                else:
                    logging.warning(f"scheme {self._scheme} not present in json file")
            with TblHistory(self._species) as isolates_history_psql_tbl:
                isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Typing results inserted'))
            logging.info('Typing results insertion succesful')
            self._insert_summary_results_in_analysis()
            logging.info('Typing summary results insertion succesful')


    def _process_regular_typing_scheme(self) -> None:
        """
        Processes regular typing scheme results
        :return: None
        """
        for locus in self._json_report_dict[self._scheme]['loci']:
            if locus['Locus'] not in self._locusset:
                if locus['% Identity'] == '100.00' and locus['HSP/Locus length'] != '-' and eval(
                        locus['HSP/Locus length']) == 1.0 and locus['Allele'] != 0 and locus['Allele'] != '?':
                    self._isolates_ad_psql_tbl.insert_designation_by_isolatename(
                        (locus['Locus'].replace("'", ""), self._isolatename, locus['Allele']))
                    self._locusset.add(locus['Locus'])
                # the elif below is specific to Listeria pcr serogroup where 0's are included in the profiles
                # (absent loci are required to define profiles)
                # Bigsdb creates a null allele itself in the seqdef database
                elif ((self._scheme == 'pcr_serogroup' or (self._scheme == 'bast' and locus['Locus'] == 'NadA_peptide'))
                      and locus['% Identity'] == '-' and locus['HSP/Locus length'] == '-') or self._scheme == 'cgmlst':
                    # in cgmlst you can have perfect multihits (?) that are then also considered as a zero in the custom profile by Benoit, that's why it's outside of the ( )
                    self._isolates_ad_psql_tbl.insert_designation_by_isolatename(
                        (locus['Locus'], self._isolatename, '0'))
                    self._locusset.add(locus['Locus'])

    def _process_irregular_typing_scheme(self) -> None:
        """
        Inserts irregular typing schemes into BIGSdb by pathogen.
        :return: None
        """
        if self._species == 'mycobacterium':
            self.__process_irregular_typing_scheme_mycobacterium_specific()
        elif self._species == 'neisseria':
            self.__process_irregular_typing_scheme_neisseria_specific()
        elif self._species == 'salmonella':
            self.__process_irregular_typing_scheme_salmonella_specific()

    def _process_rmlst_identification(self) -> None:
        """
        Inserts taxonomy identification based on rMLST in eav fields related tables
        :return: None
        """
        if 'rmlst' in self._json_report_dict:
            self._insert_analysis_results(self.__get_isolate_id(), 'rmlst', self._schemedict[self._scheme])

    def _process_mob_suite(self) -> None:
        """
        Insert MOB-Suite results into the analysis_results table of BIGSdb.
        :return: None
        """
        plasmid_list = self._json_report_dict['mob_suite'].get('mob_suite_overview')
        if not plasmid_list:
            return
        self._insert_analysis_results(self.__get_isolate_id(), 'mob_suite', self._schemedict[self._scheme])

    def __get_isolate_id(self) -> str:
        """
        return BIGSdb id of the isolate
        :return: BIGSdb id of the isolate
        """
        with TblIsolates(self._species) as isolates_tbl:
            bigsdb_id = isolates_tbl.select_id_for_isolate((self._isolatename,))
        return str(bigsdb_id[0][0])

    def __process_irregular_typing_scheme_mycobacterium_specific(self) -> None:
        """
        Processes and inserts mycobacterium results
        :return: None
        """
        if self._scheme == 'spoligotyping':
            for index, allele_id in enumerate(self._json_report_dict[self._scheme]['spoligotype_binary'], 1):
                locus = ''.join(['Spacer', str(index).zfill(2)])
                self._isolates_ad_psql_tbl.insert_designation_by_isolatename((locus, self._isolatename, str(allele_id)))
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'spoligotype_binary',
                                                             self._json_report_dict[self._scheme][
                                                                 'spoligotype_binary']))
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'spoligotype_octal',
                                                             self._json_report_dict[self._scheme][
                                                                 'spoligotype_octal']))
        elif self._scheme == 'csb_rd':
            for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                locus = record.rstrip(
                    '_detected')  # need to be careful with rstrip and strip but in this case no issue
                allele_id = '1' if self._json_report_dict[self._scheme][record] else '0'
                self._isolates_ad_psql_tbl.insert_designation_by_isolatename((locus, self._isolatename, allele_id))
        elif self._scheme == 'amr_detection':
            # make a dict with field and tsv names to be able to insert
            with TblEavFields(self._species) as isolates_eavf_psql_tbl:
                fields = isolates_eavf_psql_tbl.select_fields_amr()
            amr_metadata_fields = {}
            for field in fields:
                if field[0].startswith('amr'):
                    amr_metadata_fields[field[0]] = field[0]
                else:
                    amr_metadata_fields[field[0]] = ''.join(['amr_pheno_', field[0].split('_')[-1]])
            for bigsdbname, jsonname in amr_metadata_fields.items():
                print(self._json_report_dict[self._scheme])
                self._isolates_eavt_psql_tbl.insert_eav_isolate(
                    (self._isolatename, bigsdbname, self._json_report_dict[self._scheme][jsonname]))
            # AMR results
            with TblSchemeMembers(self._species, 'isolates') as isolates_schememembers_psql_tbl:
                amr_loci = isolates_schememembers_psql_tbl.select_loci_amr()
            for locus in amr_loci:
                jsonname = '_'.join(['amr_mutations', str(locus[0]).replace('_int', '_(int.)')])
                if self._json_report_dict[self._scheme][jsonname] != '-':
                    variantsset = set()
                    for variant in self._json_report_dict[self._scheme][jsonname].split(', '):
                        variantreformatted = re.sub('[(]|[)]', '_', variant)
                        # Bert explained that if the change is found in promotor, then it can change signs
                        # And also honestly the db is really discrepant, e.g. how likely is this:
                        # Rv1979c AA G_107_A Rv1979c_AA_G_107_A Uncertain significance CFZ CFZ_Uncertain_significance
                        # Rv1979c PROM g_-107_a Rv1979c_PROM_g_-107_a Uncertain significance CFZ CFZ_Uncertain_significance
                        # + there are really just duplicates in the db so I limit to 1, then it's always the same.
                        # Sometimes not only the sign changes when it's in a promotor, but also the location,
                        # easiest solution is just to insert after it is found.
                        self._insert_dummy_sequence_if_needed(locus[0], variantreformatted)
                        if variantreformatted not in variantsset:
                            self._isolates_ad_psql_tbl.insert_designation_by_isolatename(
                                (locus[0], self._isolatename, variantreformatted))
                            variantsset.add(variantreformatted)
        elif self._scheme == 'hsp65':
            if len(self._json_report_dict[self._scheme]['loci']) != 0:
                species_set = set()
                with TblEavFields(self._species) as isolates_eavf_psql_tbl, TblEavBoolean(self._species) as isolates_eavb_psql_tbl:
                    for locus in self._json_report_dict[self._scheme]['loci']:
                        hit = '_'.join(['hsp65', locus['Species'].strip('"').replace(' ', '_').replace('.', '')])
                        if hit not in species_set:
                            if not (isolates_eavf_psql_tbl.exists_in_eav_field((hit, 'hsp65'))):
                                isolates_eavf_psql_tbl.insert_boolean_field((hit,'hsp65'))
                            isolates_eavb_psql_tbl.insert_eav_isolate((self._isolatename, hit, 't'))
                            species_set.add(hit)
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
            if len(self._json_report_dict[self._scheme]['loci']) != 0:
                for hit in self._json_report_dict[self._scheme]['loci']:
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
        if self._scheme == 'serogroup' and self._json_report_dict['serogroup']['serogroup_capsule_genes'] != "":
            scheme = self._schemedict[self._scheme]['schemename_bigsdb']
            for gene in self._json_report_dict['serogroup']['serogroup_capsule_genes'].split(','):
                self.insert_locus_if_needed(f'{scheme}_{gene}', scheme)
                self._insert_dummy_sequence_if_needed(f'{scheme}_{gene}', '1')
                self._isolates_ad_psql_tbl.insert_designation_by_isolatename((f'{scheme}_{gene}', self._isolatename, '1'))
        elif self._scheme == 'gmats' and self._json_report_dict['gmats']['gmats_status'] != "":
            with TblEavText(self._species) as isolates_eav_psql_tbl:
                clean_gmat_status = self._json_report_dict['gmats']['gmats_status'].replace('_', ' ')
                isolates_eav_psql_tbl.insert_eav_isolate((self._isolatename, 'gMATS status', clean_gmat_status))
        elif self._scheme == 'mendevar':
            bexsero_status = self._json_report_dict['mendevar'].get('mendevar_bexsero_status')
            trumenba_status = self._json_report_dict['mendevar'].get('mendevar_trumenba_status')
            with TblEavText(self._species) as isolates_eav_psql_tbl:
                if bexsero_status:
                    isolates_eav_psql_tbl.insert_eav_isolate((self._isolatename, 'MenDeVar Bexsero status', bexsero_status.replace('_', ' ')))
                if trumenba_status:
                    isolates_eav_psql_tbl.insert_eav_isolate((self._isolatename, 'MenDeVar Trumenba status', trumenba_status.replace('_', ' ')))

    def __process_irregular_typing_scheme_salmonella_specific(self) -> None:
        """
        Processes and inserts Salmonella results
        :return: None
        """
        if self._scheme == 'mykrobe':
            self._insert_analysis_results(self.__get_isolate_id(), self._scheme, self._schemedict[self._scheme])

        elif self._scheme == 'sistr':
            serotyping_insert = self._json_report_dict[self._scheme]['sistr_serotype_antigenic_formula']
            if serotyping_insert != '-':
                self.___salmonella_insert_antigens_into_db(serotyping_insert)
            self._insert_analysis_results(self.__get_isolate_id(), self._scheme, self._schemedict[self._scheme])

        elif self._scheme == 'seqsero2':
            for mode in ['kmer', 'kmerread', 'allele']:
                serotyping_insert = self._json_report_dict['seqsero2'].get(
                    f'{self._scheme}_{mode}_Predicted_antigenic_profile')
                if serotyping_insert:
                    self.___salmonella_insert_antigens_into_db(serotyping_insert, mode)
            self._insert_analysis_results(self.__get_isolate_id(), self._scheme, self._schemedict[self._scheme])

        elif self._scheme == 'spifinder':
            for mode in ['fastq', 'fasta']:
                hits: List = self._json_report_dict['spifinder'].get(f'{self._scheme}_{mode}')
                if hits == 'n/a':
                    continue
                if hits and len(hits) != 0:
                    inserted_alleledesignations_list = set()
                    for spi in hits:
                        spifinder_entry = f"CatFunc{spi['category_function']}__{spi['accession']}"
                        spifinder_field = f"{self._scheme}_{mode}_{spi['SPI']}".upper()
                        if spifinder_entry not in inserted_alleledesignations_list:
                            self._insert_dummy_sequence_if_needed(spifinder_field, spifinder_entry)
                            self._isolates_ad_psql_tbl.insert_designation_by_isolatename(
                                (spifinder_field, self._isolatename, spifinder_entry))
                            inserted_alleledesignations_list.add(spifinder_entry)

        elif self._scheme == 'abritamr':
            self._insert_analysis_results(self.__get_isolate_id(), self._scheme, self._schemedict[self._scheme])

    def ___salmonella_insert_antigens_into_db(self, raw_formula: str,
                                              mode: Optional[ModeValue] = None) -> None:
        """
        Inserts antigens separately from the formula
        :param raw_formula: serotype formula O:H1:H2
        :param mode: Seqsero2 specific parameter to differentiate between the three different modes that it is run in.
        :return: None
        """
        if mode is not None:
            validate_literal(mode, ModeLiteral)
        raw_formula_splitted: List = raw_formula.split(':')
        antigensdict = {"O_antigen": raw_formula_splitted[0].split(','),
                        "H1_antigen": raw_formula_splitted[1].split(','),
                        "H2_antigen": raw_formula_splitted[2].split(',')}
        antigens = ["O_antigen", "H1_antigen", "H2_antigen"]
        for antigen in antigens:
            field = f'{self._scheme}_{antigen}'.upper() if not mode else f'{self._scheme}_{mode}_{antigen}'.upper()
            entries = antigensdict[antigen]
            for entry in entries:
                if entry != '-':
                    self._insert_dummy_sequence_if_needed(field, entry)
                    self._isolates_ad_psql_tbl.insert_designation_by_isolatename((field, self._isolatename, entry))
