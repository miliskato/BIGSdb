import dataclasses
import datetime
import logging
import socket
from typing import Any, Dict

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from .json_superclass import JsonSuperClass
from .psql import TblEavBoolean, TblEavFields, TblEavInt, TblEavText, TblEavTextHidden, TblHistory, TblIsolates
from ..utils.html_tbl_templates import HtmlAntiviralAssociationsTableBuilder, HtmlAntiviralMutationsTableBuilder, HtmlRefSelectionTableBuilder, HtmlReportBuilder
from ..utils.url_helper import UrlHelper


@dataclasses.dataclass
class MainInserterContext:
    """
    Class used to keep the value of the isolate_id and the report url which are defined in the context of the main class.
    Called when these values are already defined to replace the inheritance, which is not possible for variables defined by a method of the class.
    """
    isolate_id: str
    report_url: str


class MainInserter(JsonSuperClass):
    """
    Class containing definitions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename: str, species: str, json_report_dict: JsonReportDict, config_data: Dict[str, Any],
                 report_access: str, vcf_path: str, viral_species: bool) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param json_report_dict: results of sample
        :param report_access: report_directory from MongoDB
        :param vcf_path: subdirectory containing the vcf file
        :param viral_species: True if species is viral, False if species is bacterial
        :return: None
        """
        super().__init__(isolatename, species, json_report_dict, config_data)
        self._report_access = report_access
        self._vcf_path = vcf_path
        self._viral_species = viral_species

    def insert_new_isolate(self, uploader_mail_address: str, isolation_date: str) -> None:
        """
        main function to insert a new isolate, but only the isolate
        :param uploader_mail_address: mailadress of the uploader of the new isolate
        :param isolation_date: isolation date as str as DD/MM/YYYY
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            sample_presence = isolates_psql_tbl.count_isolate((self._isolatename,))
            if sample_presence[0][0] == 0:
                isolates_psql_tbl.insert_isolate((self._isolatename, uploader_mail_address,  # todo should uploader mail address not removed?
                                                  datetime.datetime.strptime(self._json_report_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'),
                                                  datetime.datetime.strptime(isolation_date, '%d/%m/%Y').strftime('%Y-%m-%d')))
                with TblHistory(self._species) as isolates_history_psql_tbl:
                    isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Isolate record added'))
            else:
                raise RuntimeError(f"isolatename {self._isolatename} of {self._species} already exists on host {socket.gethostname()}")

        self.__insert_main_metadata()

    def update_isolate_analysis_date(self) -> None:
        """
        Insert a new isolate version for an existing isolate
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            isolates_psql_tbl.update_isolate_analysis_date(
                (datetime.datetime.strptime(self._json_report_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), self._isolatename))
        self.__insert_main_metadata()

    def __create_context(self) -> MainInserterContext:
        """
        Method which is used to return the MainInserterContext object. By essence, private, as this one cannot be used outside the context of the class.
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            isolate_tuple = isolates_psql_tbl.select_id_for_isolate((self._isolatename,))
            isolate_id = str(isolate_tuple[0][0])
            return MainInserterContext(isolate_id, UrlHelper.report_for_isolate(self._species, isolate_id))

    def __insert_main_metadata(self) -> None:
        """
        Inserts the main metadata into bigsdb for an isolate
        :return: None
        """

        context = self.__create_context()

        with TblEavText(self._species) as self._isolates_eavt_psql_tbl, \
                TblIsolates(self._species) as self.isolates_psql_tbl, TblEavInt(self._species) as self._isolates_eavi_psql_tbl:

            report_link = f'<p><a href="{context.report_url}" target="_blank"> html report</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'html', report_link))
            if self._viral_species:
                assemblylink = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self._species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={context.isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">consensus sequence</a></p>'
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'consensus_sequence', assemblylink))
            else:
                assemblylink = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self._species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={context.isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">assembly</a></p>'
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'assembly', assemblylink))
            self.__insert_species_specific_metadata(context)
            if 'changed_version' in self._json_report_dict:
                with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                    isolates_eavth_psql_tbl.insert_hidden_isolate((self._isolatename, 'mongo_results_version', self._json_report_dict['changed_version']))
            if 'validation' in self._json_report_dict:
                self.isolates_psql_tbl.add_validation((self._json_report_dict['validation']['type'], self._json_report_dict['validation']['curator'],
                                                       datetime.datetime.strptime(self._json_report_dict['validation']['date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'),
                                                       str(context.isolate_id)))
            logging.info('Metadata insertion successful')

    def __insert_species_specific_metadata(self, context: MainInserterContext) -> None:
        """
        Insert species specific metadata
        :return: None
        """
        # TODO use insert_eav_id and use the context.isolate_id to avoid unnecessary postgres query
        if self._species == 'mycobacterium':
            # tsv input (only this way in tsv output)
            if '51SNP-gyrB_group' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'gyrB_group', self._json_report_dict['51SNP-gyrB_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Genetic_group', self._json_report_dict['51SNP-genetic_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'SCG', self._json_report_dict['51SNP-scg']))
            # json input (only this way in json output)
            elif '51_snp' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'gyrB_group', self._json_report_dict['51_snp']['51SNP-gyrB_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Genetic_group', self._json_report_dict['51_snp']['51SNP-genetic_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'SCG', self._json_report_dict['51_snp']['51SNP-scg']))
            # tsv input
            if 'snpit_species' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_species', self._json_report_dict['snpit_species']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_lineage', self._json_report_dict['snpit_lineage']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_sublineage', self._json_report_dict['snpit_sublineage']))
            # json input
            elif 'snpit' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_species', self._json_report_dict['snpit']['snpit_species']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_lineage', self._json_report_dict['snpit']['snpit_lineage']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_sublineage', self._json_report_dict['snpit']['snpit_sublineage']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_percent_matched', self._json_report_dict['snpit']['snpit_percent_matched']))
            if 'snp_lineage' in self._json_report_dict:
                lineage_dict = self._json_report_dict['snp_lineage']['detected_lineage_by_level']
                lineage_keys = list({e for e in lineage_dict if lineage_dict[e]})
                for k in lineage_keys:
                    self._isolates_eavi_psql_tbl.insert_eav_int_isolate((self._isolatename, lineage_dict[k]['lineage']['id_'], lineage_dict[k]['count']))
        elif self._species == 'neisseria':
            # json input
            if 'serogroup' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serogroup_legacy', self._json_report_dict['serogroup']['serogroup_legacy']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serogroup_capsule', self._json_report_dict['serogroup']['serogroup_capsule']))
        elif self._species == 'influenza':
            if 'nextclade' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate_viral_species(
                    (self._isolatename, 'influenza_subtype', self._json_report_dict['nextclade'].get('nextclade_detected_subtype')))
                self._isolates_eavt_psql_tbl.insert_eav_isolate_viral_species((self._isolatename, 'nextclade_clade', self._json_report_dict['nextclade'].get('nextclade_clade')))
            if 'antivirals' in self._json_report_dict:
                antiviral_mutations = self._json_report_dict['antivirals'].get('antivirals_mutations')
                if antiviral_mutations:
                    antiviral_associations = self._json_report_dict['antivirals'].get('antivirals_associations')
                    antiviral_mutations_table_builder = HtmlAntiviralMutationsTableBuilder(context.report_url)
                    antiviral_associations_table_builder = HtmlAntiviralAssociationsTableBuilder(context.report_url)
                    for item in antiviral_mutations:
                        antiviral_mutations_table_builder.add_mutation(item['subtype'], item['segment'], item['type'], item['mutation'])
                    with TblEavFields(self._species) as isolates_eavf_psql_tbl, TblEavBoolean(self._species) as isolates_eavb_psql_tbl:
                        for item in antiviral_associations:
                            antiviral_associations_table_builder.add_association(item['category'], item['key'], item['antiviral'], item['resistance'])
                            antiviral_key_search = f'{item['antiviral']}_{item['resistance']}'
                            if not isolates_eavf_psql_tbl.exists_in_eav_field((antiviral_key_search, 'bool')):
                                isolates_eavf_psql_tbl.insert_boolean_field((antiviral_key_search, 'antiviral_for_query'))
                            isolates_eavb_psql_tbl.insert_eav_isolate((self._isolatename, antiviral_key_search, 't'))
                    report_builder = HtmlReportBuilder()
                    report_builder.add_title("Detected mutations")
                    report_builder.add_table(antiviral_mutations_table_builder)
                    report_builder.add_title("Subsequent associations")
                    report_builder.add_table(antiviral_associations_table_builder)
                    html = report_builder.build()
                    self._isolates_eavt_psql_tbl.insert_eav_isolate_viral_species((self._isolatename, 'Antiviral_resistances', html))
            if 'ref_selection' in self._json_report_dict:
                ref_selection_table_builder = HtmlRefSelectionTableBuilder(context.report_url)
                for key, value in self._json_report_dict['ref_selection'].items():
                    if isinstance(value, str):
                        continue
                    segment = key.split('-')[-1]
                    metadata = value['metadata']
                    ref_selection_table_builder.add_segment(segment, value['ref_id_fmt'], value['median_mult'], value['hashes'], metadata['Strain'], metadata['Type'])
                html = ref_selection_table_builder.build()
                self._isolates_eavt_psql_tbl.insert_eav_isolate_viral_species((self._isolatename, 'reference_selection', html))

        elif self._species.startswith('enterococcus'):
            if 'lrefinder' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'LRE-Finder_species', self._json_report_dict['lrefinder'].get('lrefinder_species')))
            if 'bacmet' in self._json_report_dict and self._json_report_dict['bacmet']['bacmet_genes'] != '':
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'BacMet_genes', self._json_report_dict['bacmet']['bacmet_genes']))
