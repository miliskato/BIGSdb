import logging
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Union

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from .json_superclass import JsonSuperClass
from .psql import TblAlleleDesignations, TblHistory, TblIsolates
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
        self._isolate_id = self.__get_isolate_id()

    def insert_typing_results(self) -> None:
        """
        Inserts typing results into bigsdb from json
        :return: None
        """
        with TblAlleleDesignations(self._species) as self._isolates_ad_psql_tbl:
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
                elif self._scheme == 'bacmet_results':
                    self._process_bacmet()
                elif self._scheme == 'krona':
                    self._process_krona()
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
        elif self._species == 'influenza':
            self.__process_irregular_typing_scheme_influenza_specific()

    def _process_rmlst_identification(self) -> None:
        """
        Inserts taxonomy identification based on rMLST in eav fields related tables
        :return: None
        """
        if 'rmlst' in self._json_report_dict:
            self._insert_analysis_results(self._isolate_id, 'rmlst', self._schemedict[self._scheme])

    def _process_mob_suite(self) -> None:
        """
        Inserts MOB-Suite results into the analysis_results table of BIGSdb.
        :return: None
        """
        plasmid_list = self._json_report_dict['mob_suite'].get('mob_suite_overview')
        if not plasmid_list:
            return
        self._insert_analysis_results(self._isolate_id, 'mob_suite', self._schemedict[self._scheme])

    def _process_krona(self) -> None:
        """
        Inserts Krona report into the analysis_results table of BIGSdb.
        :return: None
        """
        mongo_config_provider = MongoConfigProvider()
        dtap = mongo_config_provider.dtap
        file = f'/{dtap}/{self._species}/{self._isolatename}/contamination_check/krona_report.html'
        report_url = UrlHelper.file_from_report_for_isolate(self._species, self._isolate_id, file)
        self._json_report_dict['krona'] = {'krona_report_url': report_url}
        self._insert_analysis_results(self._isolate_id, 'krona', self._schemedict[self._scheme], False)

    def _process_bacmet(self) -> None:
        """
        Insert BacMet results into the analysis_results table of BIGSdb.
        :return: None
        """
        if 'bacmet' in self._json_report_dict and self._json_report_dict['bacmet']['bacmet_genes'] != '':
            self._insert_analysis_results(self._isolate_id, 'bacmet', self._schemedict[self._scheme])

    def __get_isolate_id(self) -> str:
        """
        return BIGSdb id of the isolate
        :return: BIGSdb id of the isolate
        """
        with TblIsolates(self._species) as isolates_tbl:
            bigsdb_id = isolates_tbl.select_id_for_isolate((self._isolatename,))
        return bigsdb_id

    def __process_irregular_typing_scheme_mycobacterium_specific(self) -> None:
        """
        Processes and inserts mycobacterium results
        :return: None
        """
        if self._scheme == 'spoligotyping':
            for index, allele_id in enumerate(self._json_report_dict[self._scheme]['spoligotype_binary'], 1):
                locus = ''.join(['Spacer', str(index).zfill(2)])
                self._isolates_ad_psql_tbl.insert_designation_by_isolatename((locus, self._isolatename, str(allele_id)))
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
        elif self._scheme == 'csb_rd':
            for record in ['csb_detected', 'RD1_detected', 'RD9_detected']:
                locus = record.rstrip(
                    '_detected')  # need to be careful with rstrip and strip but in this case no issue
                allele_id = '1' if self._json_report_dict[self._scheme][record] else '0'
                self._isolates_ad_psql_tbl.insert_designation_by_isolatename((locus, self._isolatename, allele_id))
        elif self._scheme == 'hsp65' or self._scheme == 'ncbi_16s':
            if len(self._json_report_dict[self._scheme]['loci']) != 0:
                self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
        elif self._scheme in ['amr_detection', 'snpit']:
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
        elif self._scheme == '51_snp':
            snp_section = self._json_report_dict[self._scheme]
            keys_to_rename = [key for key in list(snp_section.keys()) if key.startswith('51SNP-')]
            for old_key in keys_to_rename:
                new_key = old_key.replace('51SNP-', '')
                snp_section[new_key] = snp_section.pop(old_key)
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
        elif self._scheme == 'snplineage':
            snp_lineages = self._json_report_dict[self._scheme]['snp_lineages']
            self._json_report_dict[self._scheme]['detected_lineage'] = snp_lineages.split(', ')[-1]
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])

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
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
        elif self._scheme == 'mendevar':
            bexsero_status = self._json_report_dict['mendevar'].get('mendevar_bexsero_status')
            trumenba_status = self._json_report_dict['mendevar'].get('mendevar_trumenba_status')
            if bexsero_status or trumenba_status:
                self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])

    def __process_irregular_typing_scheme_salmonella_specific(self) -> None:
        """
        Processes and inserts Salmonella results
        :return: None
        """
        if self._scheme == 'mykrobe':
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])

        elif self._scheme == 'sistr':
            serotyping_insert = self._json_report_dict[self._scheme]['sistr_serotype_antigenic_formula']
            if serotyping_insert != '-':
                self.___salmonella_insert_antigens_into_db(serotyping_insert)
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])

        elif self._scheme == 'seqsero2':
            for mode in ['kmer', 'kmerread', 'allele']:
                serotyping_insert = self._json_report_dict['seqsero2'].get(
                    f'{self._scheme}_{mode}_Predicted_antigenic_profile')
                if serotyping_insert:
                    self.___salmonella_insert_antigens_into_db(serotyping_insert, mode)
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])

        elif self._scheme == 'spifinder':
            for mode in ['fastq', 'fasta']:
                hits: list = self._json_report_dict['spifinder'].get(f'{self._scheme}_{mode}')
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
            self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])

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
        raw_formula_splitted: list = raw_formula.split(':')
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

    def __process_irregular_typing_scheme_influenza_specific(self) -> None:
        """
        Processes and inserts Influenza results.
        :return: None
        """
        if self._scheme == 'ref_selection':
            if 'ref_selection' in self._json_report_dict:
                self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
        elif self._scheme == 'nextclade':
            if 'nextclade' in self._json_report_dict:
                if self._json_report_dict['nextclade']['nextclade_detected_subtype'] == 'YAM':
                    nextclade_section = self._json_report_dict[self._scheme]
                    keys_to_rename = [key for key in list(nextclade_section.keys()) if key not in ['nextclade_detected_subtype', 'nextclade_tool_version']]
                    for old_key in keys_to_rename:
                        new_key = old_key.replace('nextclade_', 'nextclade_ha_')
                        nextclade_section[new_key] = nextclade_section.pop(old_key)
                self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
        elif self._scheme == 'antivirals':
            if 'antivirals' in self._json_report_dict:
                antiviral_mutations = self._json_report_dict['antivirals'].get('antivirals_mutations')
                if antiviral_mutations:
                    self._insert_analysis_results(self._isolate_id, self._scheme, self._schemedict[self._scheme])
