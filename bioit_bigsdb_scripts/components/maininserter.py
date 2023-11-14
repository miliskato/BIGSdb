import datetime
import logging
import numpy as np
import socket
from typing import Any, Dict, List

from .json_superclass import JsonSuperClass
from .psql import TblEavTextHidden, TblEavText, TblIsolates, TblHistory, TblSequenceBin, TblSeqBinStats, TblProjectMembers, TblEavFields, TblSchemes


class MainInserter(JsonSuperClass):
    """
    Class containing defintions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename: str, species: str, sample_output_dict: Dict[str, Any], config_data: Dict[str, Any]) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param sample_output_dict: results of sample
        :param config_data: the bigsdb config data
        :return: None
        """
        super().__init__(isolatename, species, sample_output_dict, config_data)
    
    def insert_new_isolate(self, uploadermailadress: str) -> None:
        """
        main function to insert a new isolate, but only the isolate
        :param uploadermailadress: mailadress of the uploader of the new isolate
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            isolates_psql_tbl.count_isolate((self._isolatename,))
            sample_presence = isolates_psql_tbl.count_isolate((self._isolatename,))
            if sample_presence[0][0] == 0:
                isolates_psql_tbl.insert_isolate((self._isolatename, uploadermailadress,
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
            # todo all other columns
            isolates_psql_tbl.insert_isolate_newversion((self._isolatename, self._isolatename, self._isolatename,
                                                         datetime.datetime.strptime(self._sample_output_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d')))
            isolates_psql_tbl.update_newversion([self._isolatename])
            with TblSequenceBin(self._species) as isolates_seqbin_psql_tbl:
                isolates_seqbin_psql_tbl.update_sequencebin_newversion([self._isolatename])
            with TblSeqBinStats(self._species) as isolates_seqbinstats_psql_tbl:
                isolates_seqbinstats_psql_tbl.update_seqbinstats_newversion([self._isolatename])
        with TblProjectMembers(self._species) as isolates_projectmembers_psql_tbl:
            isolates_projectmembers_psql_tbl.add_newversion_projectmembers([self._isolatename])

    def insert_main_metadata(self) -> None:
        """
        Inserts the main metadata into bigsdb for an isolate
        :return: None
        """
        with TblEavText(self._species) as self._isolates_eavt_psql_tbl,\
                TblIsolates(self._species) as self.isolates_psql_tbl:
            reportlink = f'<p><a href="/galaxyreports/{self._species}/{self._isolatename}/report.html" target="_blank"> html report</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'html', reportlink))
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'tsv', reportlink.replace('html', 'tsv')))
            vcflink_unfiltered = f'<p><a href="/galaxyreports/{self._species}/{self._isolatename}/variant_calling/variants-{self._isolatename}-all.vcf" target="_blank">VCF unfiltered</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'VCF_unfiltered', vcflink_unfiltered))
            vcflink_filtered = f'<p><a href="/galaxyreports/{self._species}/{self._isolatename}/variant_calling/variants-{self._isolatename}-filtered.vcf" target="_blank">VCF filtered</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'VCF_filtered', vcflink_filtered))
            isolate_id = self.isolates_psql_tbl.select_maxid_for_isolate((self._isolatename,))[0][0]
            assemblylink = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self._species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">assembly</a></p>'
            self._isolates_eavt_psql_tbl.insert_eav_isolate((self._isolatename, 'assembly', assemblylink))
            self._insert_species_specific_metadata()
            self._insert_naive_clustering(isolate_id)
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

    def _insert_naive_clustering(self, isolate_id: int) -> None:
        """
        Insert the distances for the existing distance fields
        :param isolate_id: id of the isolate in bigsdb
        :return: None
        """
        distance_matrix: np.array = np.load(str(self._bigsdb_config_data['naive_clustering_distance_matrix_file']).
                                            replace('species', self._species))
        # extract row
        row_cgst = distance_matrix[self._sample_output_dict['cgST'] - 1]
        with TblEavFields(self._species) as isolates_eavf_psql_tbl:
            cgmlst_diff_fields = isolates_eavf_psql_tbl.select_fields_cgmlstdifferences()
        with TblSchemes(self._species, 'isolates') as isolates_schmemes_psql_tbl:
            cgmlst_bigsdb_schemeid = isolates_schmemes_psql_tbl.select_scheme_id_cgmlst()[0][0]
        for field in cgmlst_diff_fields:
            interval = field[0].split('_')[-1]
            interval_start = int(interval.split('-')[0])
            interval_stop = int(interval.split('-')[-1])
            # get all cgSTs within distance
            indices = np.where((row_cgst >= interval_start) & (row_cgst <= interval_stop))[0]
            if len(indices) > 0:
                if interval != '0':
                    indices = np.append(indices, self._sample_output_dict['cgST'] - 1)
                html = self.__generate_htmlfield_cgstquery([x + 1 for x in indices],
                                                           cgmlst_bigsdb_schemeid)
                with TblEavText(self._species) as isolates_eavt_psql_tbl:
                    isolates_eavt_psql_tbl.insert_eav_id((str(isolate_id), field[0], html))

    def __generate_htmlfield_cgstquery(self, cgsts: List[int], cgmlst_bigsdb_schemeid: int) -> str:
        """
        Generates an html field to be inserted into bigsdb that will query all isolates with certain cgSTs
        :param cgsts: the cgST's that should be included in the html query
        :param cgmlst_bigsdb_schemeid: the scheme id of the cgMLST scheme in bigsdb (usually 2, after 1 mlst,
        but in the case of stec that has 2 mlst it is 3)
        :return: html query string
        """
        base_start = f' <p><a href="/cgi-bin/bigsdb/bigsdb.pl?set_id=0&page=query&submit=1&order=id&db=bigsdb_' \
                     f'{self._species}_isolates'
        base_end = '" target="_blank">query</a><p>'
        html_ref = base_start
        for index, cgst in enumerate(cgsts):
            html_ref += f"&designation_value{index+1}={cgst}&designation_field{index+1}=s_{cgmlst_bigsdb_schemeid}_cgST"
        html_ref += base_end
        return html_ref
