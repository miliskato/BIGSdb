from typing import Any, Dict, List, Literal, Optional, Tuple

from bioit_bigsdb_scripts.components.json_superclass import JsonSuperClass
from bioit_bigsdb_scripts.components.psql import TblAlleleDesignations, TblEavFields, TblEavText
from bioit_bigsdb_scripts.inserters.irregular_schemes_inserter.irregular_schemes_inserter import IrregularSchemesInserter
from bioit_bigsdb_scripts.tests.playground import isolates_psql_tbl
from bioit_mongodb_scripts.model.json_model import JsonReportDict

class SalmonellaIrregularSchemesInserter(IrregularSchemesInserter):

    SPECIES = 'salmonella'

    def accept(self, species: str) -> bool:
        """
        Evaluate if the species should be accepted.
        :param species: name of the species
        :return: True if the species should be accepted by the builder
        """
        return species == self.SPECIES

    def insert_scheme(self, species: str, scheme: str, scheme_config: Dict[str, Any], json_report: JsonReportDict, isolate_name: str) -> None:
        """
        Insert isolates results for the irregular schemes specific for Neisseria.
        """
        scheme_results = json_report[scheme]

        if scheme == 'mykrobe':
            mykrobe_results = scheme_results['mykrobe_drug_susceptibility']
            with TblEavFields(self.SPECIES) as isolates_eavf_psql_tbl:
                fields_mykrobe: List[Tuple[str]] = isolates_eavf_psql_tbl.select_fields_of_a_category(('Mykrobe',))
            for item in fields_mykrobe:
                item_in_mongo = item[0].replace('_susceptibility', '')
                if item_in_mongo in mykrobe_results:
                    susceptibility: str = \
                    mykrobe_results[item_in_mongo]['susceptibility']
                    with TblEavText(self.SPECIES) as isolates_eavt_psql_tbl:
                        isolates_eavt_psql_tbl.insert_eav_isolate((isolate_name, item[0], susceptibility))

                    mykrobe_field = 'MYKROBE_' + item_in_mongo.upper()
                    # get the genes and variants
                    future_alleles = mykrobe_results[item_in_mongo]['variants'].split(';') + mykrobe_results[item_in_mongo]['genes'].split(';')
                    for value in future_alleles:
                        if value != '-':
                            JsonSuperClass._insert_dummy_sequence_if_needed(mykrobe_field, value)
                            with TblAlleleDesignations(self.SPECIES) as isolates_ad_psql_tbl:
                                isolates_ad_psql_tbl.insert_designation_by_isolatename((mykrobe_field, isolate_name, value))

        elif scheme == 'sistr':
            serotyping_insert = scheme_results['sistr_serotype_antigenic_formula']
            if serotyping_insert != '-':
                self.__salmonella_insert_antigens_into_db(serotyping_insert)
                with TblEavText(self.SPECIES) as isolates_eavt_psql_tbl:
                    isolates_eavt_psql_tbl.insert_eav_isolate((isolate_name, f'{scheme}_formula', serotyping_insert))
            serotyping_insert = scheme_results['sistr_serotype_consensus']
            if serotyping_insert != '-':
                with TblEavText(self.SPECIES) as isolates_eavt_psql_tbl:
                    isolates_eavt_psql_tbl.insert_eav_isolate((isolate_name, f'{scheme}_serotype', serotyping_insert))

        elif scheme == 'seqsero2':
            with TblEavText(self.SPECIES) as isolates_eavt_psql_tbl:
                for mode in ['kmer', 'kmerread', 'allele']:
                    serotyping_insert = json_report['seqsero2'].get(f'{scheme}_{mode}_Predicted_antigenic_profile')
                    if serotyping_insert:
                        self.__salmonella_insert_antigens_into_db(serotyping_insert, mode)
                        if serotyping_insert != '-:-:-':
                            isolates_eavt_psql_tbl.insert_eav_isolate((isolate_name, f'{scheme}_{mode}_formula', serotyping_insert))
                        serotyping_insert = json_report['seqsero2'][f'{scheme}_{mode}_Predicted_serotype']
                        if serotyping_insert != '-_-:-:-':
                            isolates_eavt_psql_tbl.insert_eav_isolate((isolate_name, f'{scheme}_{mode}_serotype', serotyping_insert))

        elif scheme == 'spifinder':
            for mode in ['fastq', 'fasta']:
                hits: List = json_report['spifinder'].get(f'{scheme}_{mode}')
                if hits == 'n/a':
                    continue
                if hits and len(hits) != 0:
                    inserted_alleledesignations_list = set()
                    for spi in hits:
                        spifinder_entry = f"CatFunc{spi['category_function']}__{spi['accession']}"
                        spifinder_field = f"{scheme}_{mode}_{spi['SPI']}".upper()
                        if spifinder_entry not in inserted_alleledesignations_list:
                            JsonSuperClass._insert_dummy_sequence_if_needed(spifinder_field, spifinder_entry)
                            with TblAlleleDesignations(self.SPECIES) as isolates_ad_psql_tbl:
                                isolates_ad_psql_tbl.insert_designation_by_isolatename((spifinder_field, isolate_name, spifinder_entry))
                            inserted_alleledesignations_list.add(spifinder_entry)

        elif scheme == 'abritamr':
            with TblEavFields(self.SPECIES) as isolates_eavf_psql_tbl:
                fields_abritamr: List[Tuple[str]] = isolates_eavf_psql_tbl.select_fields_of_a_category(('AbritAMR',))

            for item in fields_abritamr:
                item_like_mongo = 'abritamr_' + item[0]
                if item_like_mongo in scheme_results and scheme_results[item_like_mongo] is not None:
                    amr_detection: str = scheme_results[item_like_mongo]
                    if amr_detection == '-':
                        amr_detection = 'NA'
                    with TblEavText(self.SPECIES) as isolates_eavt_psql_tbl:
                        isolates_eavt_psql_tbl.insert_eav_isolate((isolate_name, item[0], amr_detection))

    def __salmonella_insert_antigens_into_db(self, scheme: str, raw_formula: str,
                                              mode: Optional[Literal['kmer', 'kmerread', 'allele']] = None) -> None:
        """
        Inserts antigens separately from the formula
        :param raw_formula: serotype formula O:H1:H2
        :param mode: Seqsero2 specific parameter to differentiate between the three different modes that it is run in.
        :return: None
        """
        raw_formula_splitted: List = raw_formula.split(':')
        antigensdict = {"O_antigen": raw_formula_splitted[0].split(','),
                        "H1_antigen": raw_formula_splitted[1].split(','),
                        "H2_antigen": raw_formula_splitted[2].split(',')}
        antigens = ["O_antigen", "H1_antigen", "H2_antigen"]
        for antigen in antigens:
            field = f'{scheme}_{antigen}'.upper() if not mode else f'{scheme}_{mode}_{antigen}'.upper()
            entries = antigensdict[antigen]
            for entry in entries:
                if entry != '-':
                    JsonSuperClass._insert_dummy_sequence_if_needed(field, entry)
                    with TblAlleleDesignations(self.SPECIES) as isolates_ad_psql_tbl:
                        isolates_ad_psql_tbl.insert_designation_by_isolatename((field, self.isolatename, entry))