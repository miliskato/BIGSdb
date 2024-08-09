import datetime
import logging
import socket
from typing import Any, Dict

from .json_superclass import JsonSuperClass
from .psql import TblEavTextHidden, TblEavText, TblIsolates, TblHistory, TblSequenceBin, TblSeqBinStats


class MainInserter(JsonSuperClass):
    """
    Class containing defintions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename: str, species: str, sample_output_dict: Dict[str, Any], config_data: Dict[str, Any], report_access: str, vcf_path: str, mongo_dtap: str) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param sample_output_dict: results of sample
        :param report_access: report_directory from MongoDB
        :param vcf_path: subdirectory containing the vcf file
        :param mongo_dtap: dtap from mongo config
        :return: None
        """
        super().__init__(isolatename, species, sample_output_dict, config_data)
        self._report_access = report_access
        self._vcf_path = vcf_path
        self._mongo_dtap = mongo_dtap
    
    def insert_new_isolate(self, uploader_mail_address: str) -> None:
        """
        main function to insert a new isolate, but only the isolate
        :param uploader_mail_address: mailadress of the uploader of the new isolate
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            sample_presence = isolates_psql_tbl.count_isolate((self._isolatename,))
            if sample_presence[0][0] == 0:
                isolates_psql_tbl.insert_isolate((self._isolatename, uploader_mail_address,
                                                  datetime.datetime.strptime(self._sample_output_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d')))
                with TblHistory(self._species) as isolates_history_psql_tbl:
                    isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Isolate record added'))
            else:
                raise RuntimeError(f"isolatename {self._isolatename} of {self._species} already exists on host {socket.gethostname()}")

    def insert_new_isolate_version(self) -> None:
        """
        Insert a new isolate version for an existing isolate
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            isolates_psql_tbl.insert_isolate_newversion((datetime.datetime.strptime(self._sample_output_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), self._isolatename))


    def insert_main_metadata(self) -> None:
        """
        Inserts the main metadata into bigsdb for an isolate
        :return: None
        """
        with TblEavText(self._species) as self._isolates_eavt_psql_tbl,\
                TblIsolates(self._species) as self.isolates_psql_tbl:
            mongo_report_field = self._report_access
            dtap = self._mongo_dtap
            local_path = 'reports'
            galaxy_report_access = mongo_report_field.replace(local_path,"galaxyreports")
            azure_path = f'results/{dtap}'
            galaxy_report_access = galaxy_report_access.replace(azure_path, "galaxyreports")

            vcf_access = self._vcf_path.replace(local_path,"galaxyreports")
            vcf_access = self._vcf_path.replace(azure_path, "galaxyreports")
            vcf_unfiltered_access = vcf_access.replace('filtered','all')

            reportlink = f'<p><a href="{galaxy_report_access}/report.html" target="_blank"> html report</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'html', reportlink))
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'tsv', reportlink.replace('html', 'tsv')))
            vcflink_unfiltered = f'<p><a href="{vcf_unfiltered_access}" target="_blank">VCF unfiltered</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'VCF_unfiltered', vcflink_unfiltered))
            vcflink_filtered = f'<p><a href="{vcf_access}" target="_blank">VCF filtered</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'VCF_filtered', vcflink_filtered))
            isolate_id = self.isolates_psql_tbl.select_id_for_isolate((self._isolatename,))[0][0]
            assemblylink = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self._species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">assembly</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'assembly', assemblylink))
            self._insert_species_specific_metadata()
            if 'changed_version' in self._sample_output_dict:
                with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                    isolates_eavth_psql_tbl.insert_hidden_isolate((self._isolatename, 'mongo_results_version', self._sample_output_dict['changed_version']))
            if 'validation' in self._sample_output_dict:
                self.isolates_psql_tbl.add_validation((self._sample_output_dict['validation']['type'], self._sample_output_dict['validation']['curator'],
                                                       datetime.datetime.strptime(self._sample_output_dict['validation']['date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), str(isolate_id)))
            logging.info('Metadata insertion succesful')
    
    def _insert_species_specific_metadata(self) -> None:
        """
        Insert species specific metadata
        :return: None
        """
        if self._species == 'mycobacterium':
            # tsv input (only this way in tsv output)
            if '51SNP-gyrB_group' in self._sample_output_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'gyrB_group', self._sample_output_dict['51SNP-gyrB_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Genetic_group', self._sample_output_dict['51SNP-genetic_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'SCG', self._sample_output_dict['51SNP-scg']))
            # json input (only this way in json output)
            elif '51SNP' in self._sample_output_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'gyrB_group', self._sample_output_dict['51SNP']['51SNP-gyrB_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Genetic_group', self._sample_output_dict['51SNP']['51SNP-genetic_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'SCG', self._sample_output_dict['51SNP']['51SNP-scg']))
            # tsv input
            if 'snpit_species' in self._sample_output_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_species', self._sample_output_dict['snpit_species']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_lineage', self._sample_output_dict['snpit_lineage']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_sublineage', self._sample_output_dict['snpit_sublineage']))
            # json input
            elif 'snpit' in self._sample_output_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_species', self._sample_output_dict['snpit']['snpit_species']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_lineage', self._sample_output_dict['snpit']['snpit_lineage']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'snpit_sublineage', self._sample_output_dict['snpit']['snpit_sublineage']))
        elif self._species == 'stec':
            if 'serotype' in self._sample_output_dict:
                # json input
                if 'serotype' in self._sample_output_dict['serotype']:
                    self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serotype', self._sample_output_dict['serotype']['serotype']))
                # tsv input
                else:
                    self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serotype', self._sample_output_dict['serotype']))
        elif self._species == 'neisseria':
            # tsv input
            if 'detected_serogroup' in self._sample_output_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serogroup', self._sample_output_dict['detected_serogroup']))
            # json input
            elif 'serogroup' in self._sample_output_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serogroup', self._sample_output_dict['serogroup']['detected_serogroup']))
