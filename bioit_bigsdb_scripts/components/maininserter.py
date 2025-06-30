import datetime
import logging
import socket
from typing import Any, Dict

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from bioit_mongodb_scripts.util.python_utility_functions import is_viral
from .json_superclass import JsonSuperClass
from .psql import TblEavInt, TblEavText, TblEavTextHidden, TblHistory, TblIsolates
from ..utils.url_helper import UrlHelper


class MainInserter(JsonSuperClass):
    """
    Class containing defintions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename: str, species: str, json_report_dict: JsonReportDict, config_data: Dict[str, Any],
                 report_access: str, vcf_path: str, mongo_dtap: str) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param json_report_dict: results of sample
        :param report_access: report_directory from MongoDB
        :param vcf_path: subdirectory containing the vcf file
        :param mongo_dtap: dtap from mongo config
        :return: None
        """
        super().__init__(isolatename, species, json_report_dict, config_data)
        self._report_access = report_access
        self._vcf_path = vcf_path
        self._mongo_dtap = mongo_dtap

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

    def update_isolate_analysis_date(self) -> None:
        """
        Insert a new isolate version for an existing isolate
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            isolates_psql_tbl.update_isolate_analysis_date((datetime.datetime.strptime(self._json_report_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), self._isolatename))

    def insert_main_metadata(self) -> None:
        """
        Inserts the main metadata into bigsdb for an isolate
        :return: None
        """
        with TblEavText(self._species) as self._isolates_eavt_psql_tbl,\
                TblIsolates(self._species) as self.isolates_psql_tbl, TblEavInt(self._species) as self._isolates_eavi_psql_tbl:

            with TblIsolates(self._species) as isolates_psql_tbl:
                isolate_id = isolates_psql_tbl.select_id_for_isolate((self._isolatename,))
            report_url = UrlHelper.report_for_isolate(self._species, str(isolate_id[0][0]))
            report_link = f'<p><a href="{report_url}" target="_blank"> html report</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'html', report_link))
            isolate_id = self.isolates_psql_tbl.select_id_for_isolate((self._isolatename,))[0][0]
            if is_viral(self._species):
                assemblylink = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self._species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">consensus sequence</a></p>'
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'consensus_sequence', assemblylink))
            else:
                assemblylink = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self._species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">assembly</a></p>'
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'assembly', assemblylink))
            self._insert_species_specific_metadata()
            if 'changed_version' in self._json_report_dict:
                with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                    isolates_eavth_psql_tbl.insert_hidden_isolate((self._isolatename, 'mongo_results_version', self._json_report_dict['changed_version']))
            if 'validation' in self._json_report_dict:
                self.isolates_psql_tbl.add_validation((self._json_report_dict['validation']['type'], self._json_report_dict['validation']['curator'],
                     datetime.datetime.strptime(self._json_report_dict['validation']['date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), str(isolate_id)))
            logging.info('Metadata insertion successful')

    def _insert_species_specific_metadata(self) -> None:
        """
        Insert species specific metadata
        :return: None
        """
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
                self._isolates_eavt_psql_tbl.insert_eav_isolate_viral_species((self._isolatename, 'influenza_subtype', self._json_report_dict['nextclade'].get('nextclade_detected_subtype')))
                self._isolates_eavt_psql_tbl.insert_eav_isolate_viral_species((self._isolatename, 'nextclade_clade', self._json_report_dict['nextclade'].get('nextclade_clade')))
