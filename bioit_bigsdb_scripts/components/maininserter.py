import datetime
import logging
import socket
from pathlib import Path
from typing import Any, Dict

import numpy as np

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from bioit_mongodb_scripts.util.new_clustering_info_to_bigs import NewClusteringInfoToBigs
from .json_superclass import JsonSuperClass
from .psql import TblEavFields, TblEavTextHidden, TblEavInt, TblEavText, TblIsolates, TblHistory, TblSchemes


class MainInserter(JsonSuperClass):
    """
    Class containing defintions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename: str, species: str, json_report_dict: JsonReportDict, config_data: Dict[str, Any],
                 report_access: str, vcf_path: str, mongo_dtap: str, naive_clustering_distance_matrix_file: Path) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param json_report_dict: results of sample
        :param report_access: report_directory from MongoDB
        :param vcf_path: subdirectory containing the vcf file
        :param mongo_dtap: dtap from mongo config
        :param naive_clustering_distance_matrix_file: The path to the naive clustering cgmlst distance matrix file
        :return: None
        """
        super().__init__(isolatename, species, json_report_dict, config_data)
        self._report_access = report_access
        self._vcf_path = vcf_path
        self._mongo_dtap = mongo_dtap
        self._naive_clustering_distance_matrix_file = naive_clustering_distance_matrix_file
    
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
                                                  datetime.datetime.strptime(self._json_report_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d')))
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
            mongo_report_field = self._report_access
            dtap = self._mongo_dtap
            local_path = 'reports'
            #TODO adapt to point to bigsdb page if this option works
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
            if 'changed_version' in self._json_report_dict:
                with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                    isolates_eavth_psql_tbl.insert_hidden_isolate((self._isolatename, 'mongo_results_version', self._json_report_dict['changed_version']))
            if 'validation' in self._json_report_dict:
                self.isolates_psql_tbl.add_validation((self._json_report_dict['validation']['type'], self._json_report_dict['validation']['curator'],
                                                       datetime.datetime.strptime(self._json_report_dict['validation']['date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), str(isolate_id)))
            self._insert_naive_clustering_cgmlst_differences_fields()
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
            elif '51SNP' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'gyrB_group', self._json_report_dict['51SNP']['51SNP-gyrB_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Genetic_group', self._json_report_dict['51SNP']['51SNP-genetic_group']))
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'SCG', self._json_report_dict['51SNP']['51SNP-scg']))
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
        elif self._species == 'stec':
            if 'serotype' in self._json_report_dict:
                # json input
                if 'serotype' in self._json_report_dict['serotype']:
                    self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serotype', self._json_report_dict['serotype']['serotype']))
                # tsv input
                else:
                    self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serotype', self._json_report_dict['serotype']))
        elif self._species == 'neisseria':
            # tsv input
            if 'detected_serogroup' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serogroup', self._json_report_dict['detected_serogroup']))
            # json input
            elif 'serogroup' in self._json_report_dict:
                self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'Serogroup', self._json_report_dict['serogroup']['detected_serogroup']))

    def _insert_naive_clustering_cgmlst_differences_fields(self) -> None:
        """
        Inserts the naive clustering implementation in bigsdb for the current isolate (cgMLST_differences_ field).
        :return: None
        """
        if self._json_report_dict.get('cgST'):
            # get cgmlst_diff_fields
            with TblEavFields(self._species) as isolates_eavf_psql_tbl:
                cgmlst_diff_fields = isolates_eavf_psql_tbl.select_fields_cgmlstdifferences()

            # get the cgMLST bigsdb scheme id
            with TblSchemes(self._species, 'isolates') as isolates_schemes_psql_tbl:
                cgmlst_bigsdb_scheme_id = isolates_schemes_psql_tbl.select_scheme_id_cgmlst()[0][0]

            # read distance matrix
            distance_matrix: np.array = np.load(str(self._naive_clustering_distance_matrix_file))

            for field in cgmlst_diff_fields:
                interval = field[0].split('_')[-1]
                interval_start = int(interval.split('-')[0])
                interval_stop = int(interval.split('-')[-1])

                # extract row
                row_cgst = distance_matrix[self._json_report_dict['cgST'] - 1]
                # get all cgSTs within distance
                indices = np.where((row_cgst >= interval_start) & (row_cgst <= interval_stop))[0]
                if len(indices) > 0:
                    if interval_start != 0:
                        # if interval_start != 0, then add the current cgST because it has not been picked up
                        # by the indices query, and it should be present itself (in practice up until now start is always 0)
                        indices = np.append(indices, self._json_report_dict['cgST'] - 1)
                    html = NewClusteringInfoToBigs.generate_htmlelement_cgstquery(
                        [x + 1 for x in indices], cgmlst_bigsdb_scheme_id, field[0], self._species)
                    self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, field[0], html))
