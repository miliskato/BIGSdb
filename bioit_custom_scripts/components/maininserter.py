import datetime
import logging
import socket
from typing import Any, Dict, List, Tuple, Union

import psycopg2.extensions

from .databaseconnection import DatabaseConnection
from .json_superclass import JsonSuperClass
from .psql_tables_queries import TblEavTextHidden


class MainInserter(JsonSuperClass):
    """
    Class containing defintions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename: str, species: str, isolates_psql_db: DatabaseConnection,
                 seqdef_psql_db: DatabaseConnection, sample_output_dict: Dict[str, Any]) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param isolates_psql_db: isolate database connection instance
        :param seqdef_psql_db: sequence definition database connection instance
        :param sample_output_dict: results of sample
        :return: None
        """
        JsonSuperClass.__init__(self, isolatename, species, isolates_psql_db, seqdef_psql_db, sample_output_dict)
    
    def insert_new_isolate(self, uploadermailadress: str) -> None:
        """
        main function to insert a new isolate, but only the isolate
        :param uploadermailadress: mailadress of the uploader of the new isolate
        :return: None
        """
        sqlquery = """SELECT COUNT(*) FROM isolates WHERE isolate=%s;"""
        self.isolates_psql_db.execute_query(sqlquery, (self._isolatename,))
        sample_presence: List[List[int]] = self.isolates_psql_db.fetchall()
        if sample_presence[0][0] == 0:
            sqlquery = """
                       INSERT INTO isolates(id, 
                       isolate, sender, curator, date_entered, datestamp, uploader, latest_analysis_date)
                       VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM isolates) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), 
                       %s, 1, 1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), %s, %s);"""
            self.isolates_psql_db.execute_query(sqlquery, (self._isolatename, uploadermailadress, datetime.datetime.strptime(self._sample_output_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d')))
            sqlquery = """
                       INSERT INTO history(isolate_id, timestamp, action, curator) 
                       VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s),(SELECT NOW()::TIMESTAMP), 'Isolate record added', 1);"""
            self.isolates_psql_db.execute_query(sqlquery, (self._isolatename,))
        else:
            raise RuntimeError(f"isolatename {self._isolatename} of {self._species} already exists on host {socket.gethostname()}")

    def insert_new_isolate_version(self) -> None:
        """
        Insert a new isolate version for an existing isolate
        :return: None
        """
        sqlquery = """
                   INSERT INTO isolates(id, 
                   isolate, sender, curator, date_entered, datestamp, 
                   uploader, latest_analysis_date) 
                   VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM isolates) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), 
                   %s, 1, 1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), 
                   (SELECT uploader FROM isolates WHERE isolate=%s AND id=(SELECT MAX(id) FROM isolates WHERE isolate=%s)), %s);"""
        self.isolates_psql_db.execute_query(sqlquery, (self._isolatename, self._isolatename, self._isolatename, datetime.datetime.strptime(self._sample_output_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d')))
        sqlquery = """
                   UPDATE isolates SET new_version=(SELECT MAX(id) FROM isolates WHERE isolate=%s) 
                   WHERE isolate=%s AND new_version IS NULL AND 
                   id!=(SELECT MAX(id) FROM isolates WHERE isolate=%s);"""
        self.isolates_psql_db.execute_query(sqlquery, (self._isolatename, self._isolatename, self._isolatename))
        sqlquery = """
                   UPDATE sequence_bin SET isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s) 
                   WHERE isolate_id=(SELECT MIN(id) FROM isolates WHERE id in (SELECT id FROM isolates WHERE isolate=%s ORDER BY id DESC LIMIT 2));"""
        self.isolates_psql_db.execute_query(sqlquery, (self._isolatename, self._isolatename))
        sqlquery = """
                   UPDATE seqbin_stats SET isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s) 
                   WHERE isolate_id=(SELECT MIN(id) FROM isolates WHERE id in (SELECT id FROM isolates WHERE isolate=%s ORDER BY id DESC LIMIT 2));"""
        self.isolates_psql_db.execute_query(sqlquery, (self._isolatename, self._isolatename))

    def insert_main_metadata(self) -> None:
        """
        Inserts the main metadata into bigsdb for an isolate
        :return: None
        """
        reportlink: str = f'<p><a href="/galaxyreports/{self._species}/{self._isolatename}/report.html" target="_blank"> html report</a></p>'
        self._insert_metadata('html', reportlink)
        self._insert_metadata('tsv', reportlink.replace('html', 'tsv'))
        vcflink_unfiltered: str = f'<p><a href="/galaxyreports/{self._species}/{self._isolatename}/variant_calling/variants-{self._isolatename}-all.vcf" target="_blank">VCF unfiltered</a></p>'
        self._insert_metadata('VCF_unfiltered', vcflink_unfiltered)
        vcflink_filtered: str = f'<p><a href="/galaxyreports/{self._species}/{self._isolatename}/variant_calling/variants-{self._isolatename}-filtered.vcf" target="_blank">VCF filtered</a></p>'
        self._insert_metadata('VCF_filtered', vcflink_filtered)
        sqlquery = """SELECT MAX(id) FROM isolates WHERE isolate=%s"""
        self.isolates_psql_db.execute_query(sqlquery, (self._isolatename,))
        isolate_id: str = self.isolates_psql_db.fetchall()[0][0]
        assemblylink: str = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self._species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">assembly</a></p>'
        self._insert_metadata('assembly', assemblylink)
        self._insert_species_specific_metadata()
        if 'changed_version' in self._sample_output_dict:
            with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
                isolates_eavth_psql_tbl.insert_hidden_isolate((self._isolatename, 'mongo_results_version', self._sample_output_dict['changed_version']))
        if 'validation' in self._sample_output_dict:
            sqlquery = """UPDATE isolates SET 
                          validation_type = %s, 
                          validation_curator = %s, 
                          validation_date = %s
                          WHERE id=%s;"""
            self.isolates_psql_db.execute_query(sqlquery, (self._sample_output_dict['validation']['type'], self._sample_output_dict['validation']['curator'],
                                                 datetime.datetime.strptime(self._sample_output_dict['validation']['date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), isolate_id))
        logging.info('Metadata insertion succesful')
    
    def _insert_species_specific_metadata(self) -> None:
        """
        Insert species specific metadata
        :return: None
        """
        if self._species == 'mycobacterium':
            # tsv input (only this way in tsv output)
            if '51SNP-gyrB_group' in self._sample_output_dict:
                self._insert_metadata('gyrB_group', self._sample_output_dict['51SNP-gyrB_group'])
                self._insert_metadata('Genetic_group', self._sample_output_dict['51SNP-genetic_group'])
                self._insert_metadata('SCG', self._sample_output_dict['51SNP-scg'])
            # json input (only this way in json output)
            elif '51SNP' in self._sample_output_dict:
                self._insert_metadata('gyrB_group', self._sample_output_dict['51SNP']['51SNP-gyrB_group'])
                self._insert_metadata('Genetic_group', self._sample_output_dict['51SNP']['51SNP-genetic_group'])
                self._insert_metadata('SCG', self._sample_output_dict['51SNP']['51SNP-scg'])
            # tsv input
            if 'snpit_species' in self._sample_output_dict:
                self._insert_metadata('snpit_species', self._sample_output_dict['snpit_species'])
                self._insert_metadata('snpit_lineage', self._sample_output_dict['snpit_lineage'])
                self._insert_metadata('snpit_sublineage', self._sample_output_dict['snpit_sublineage'])
            # json input
            elif 'snpit' in self._sample_output_dict:
                self._insert_metadata('snpit_species', self._sample_output_dict['snpit']['snpit_species'])
                self._insert_metadata('snpit_lineage', self._sample_output_dict['snpit']['snpit_lineage'])
                self._insert_metadata('snpit_sublineage', self._sample_output_dict['snpit']['snpit_sublineage'])
        elif self._species == 'stec':
            if 'serotype' in self._sample_output_dict:
                # json input
                if 'serotype' in self._sample_output_dict['serotype']:
                    self._insert_metadata('Serotype', self._sample_output_dict['serotype']['serotype'])
                # tsv input
                else:
                    self._insert_metadata('Serotype', self._sample_output_dict['serotype'])
        elif self._species == 'neisseria':
            # tsv input
            if 'detected_serogroup' in self._sample_output_dict:
                self._insert_metadata('Serogroup', self._sample_output_dict['detected_serogroup'])
            # json input
            elif 'serogroup' in self._sample_output_dict:
                self._insert_metadata('Serogroup', self._sample_output_dict['serogroup']['detected_serogroup'])
