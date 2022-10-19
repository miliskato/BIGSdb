import logging
import datetime
import sys
import socket
from urllib.parse import urljoin

from .json_superclass import JsonSuperClass

class MainInserter(JsonSuperClass):
    """
    Class containing defintions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename, species, cur_isolates, cur_seqdef, sample_output_dict):
        """

        :param isolatename:
        :param species:
        :param cur_isolates: isolate database connection object
        :param cur_seqdef: sequence definition database connection object
        :param sample_output_dict: results of sample
        """
        JsonSuperClass.__init__(self, isolatename, species, cur_isolates, cur_seqdef, sample_output_dict)
    
    def insert_new_isolate(self, uploadermailadress):
        self.cur_isolates.execute(f"SELECT COUNT(*) FROM isolates WHERE isolate='{self.isolatename}'")
        sample_presence = self.cur_isolates.fetchall()
        if sample_presence[0][0] == 0:
            self.cur_isolates.execute(f"INSERT INTO isolates(id, "
                                 f"isolate, sender, curator, date_entered, datestamp, uploader, latest_analysis_date)"
                                 f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM isolates)+1) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), "
                                 f"'{self.isolatename}', 1, 1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), '{uploadermailadress}', '{datetime.datetime.strptime(self.sample_output_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d')}')")
            self.cur_isolates.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                                 f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'),(SELECT NOW()::TIMESTAMP), 'Isolate record added', 1)")
        else:
            raise RuntimeError(f"isolatename {self.isolatename} of {self.species} already exists on host {socket.gethostname()}")

    def insert_new_isolate_version(self):
        self.cur_isolates.execute(
            f"INSERT INTO isolates(id, isolate, sender, curator, date_entered, datestamp, uploader, latest_analysis_date) "
            f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM isolates)+1) IS NULL THEN 1 "
            f"ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), '{self.isolatename}', 1, 1, "
            f"(SELECT CURRENT_DATE),(SELECT CURRENT_DATE), "
            f"(SELECT uploader FROM isolates WHERE isolate='{self.isolatename}' AND id=(SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}')),"
            f"'{datetime.datetime.strptime(self.sample_output_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d')}')")
        self.cur_isolates.execute(
            f"UPDATE isolates SET new_version=(SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}') "
            f"WHERE isolate='{self.isolatename}' AND new_version IS NULL AND "
            f"id!=(SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}')")
        self.cur_isolates.execute(
            f"UPDATE sequence_bin SET isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}')"
            f"WHERE isolate_id=(SELECT MIN(id) FROM isolates WHERE id in (SELECT id FROM isolates WHERE isolate='{self.isolatename}' ORDER BY id DESC LIMIT 2))")
        self.cur_isolates.execute(
            f"UPDATE seqbin_stats SET isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}')"
            f"WHERE isolate_id=(SELECT MIN(id) FROM isolates WHERE id in (SELECT id FROM isolates WHERE isolate='{self.isolatename}' ORDER BY id DESC LIMIT 2))")

    def insert_main_metadata(self):
        reportlink = f'<p><a href="/galaxyreports/{self.species}/{self.isolatename}/report.html" target="_blank"> html report</a></p>'
        self._insert_metadata('html', reportlink)
        self._insert_metadata('tsv', reportlink.replace('html', 'tsv'))
        vcflink_unfiltered = f'<p><a href="/galaxyreports/{self.species}/{self.isolatename}/variant_calling/variants-{self.isolatename}-all.vcf" target="_blank">VCF unfiltered</a></p>'
        self._insert_metadata('VCF_unfiltered', vcflink_unfiltered)
        vcflink_filtered = f'<p><a href="/galaxyreports/{self.species}/{self.isolatename}/variant_calling/variants-{self.isolatename}-filtered.vcf" target="_blank">VCF filtered</a></p>'
        self._insert_metadata('VCF_filtered', vcflink_filtered)
        self.cur_isolates.execute(f"SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'")
        isolate_id = self.cur_isolates.fetchall()[0][0]
        assemblylink = f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?db=bigsdb_{self.species}_isolates&page=plugin&name=Contigs&format=text&isolate_id={isolate_id}&match=1&pc_untagged=0&min_length=&header=1l" target="_blank">assembly</a></p>'
        self._insert_metadata('assembly', assemblylink)
        self._insert_species_specific_metadata()
        if 'results_version' in self.sample_output_dict.keys():
            self._insert_metadata_hidden('mongo_results_version', self.sample_output_dict['mongo_results_version'])
        logging.info('Metadata insertion succesful')
    
    def _insert_species_specific_metadata(self):
        if self.species == 'mycobacterium':
            # tsv input
            if '51SNP-gyrB_group' in self.sample_output_dict:
                self._insert_metadata('gyrB_group', self.sample_output_dict['51SNP-gyrB_group'])
                self._insert_metadata('Genetic_group', self.sample_output_dict['51SNP-genetic_group'])
                self._insert_metadata('SCG', self.sample_output_dict['51SNP-scg'])
            # json input
            elif '51SNP' in self.sample_output_dict:
                self._insert_metadata('gyrB_group', self.sample_output_dict['51SNP']['51SNP-gyrB_group'])
                self._insert_metadata('Genetic_group', self.sample_output_dict['51SNP']['51SNP-genetic_group'])
                self._insert_metadata('SCG', self.sample_output_dict['51SNP']['51SNP-scg'])
            # tsv input
            if 'snpit_species' in self.sample_output_dict:
                self._insert_metadata('snpit_species', self.sample_output_dict['snpit_species'])
                self._insert_metadata('snpit_lineage', self.sample_output_dict['snpit_lineage'])
                self._insert_metadata('snpit_sublineage', self.sample_output_dict['snpit_sublineage'])
            # json input
            elif 'snpit' in self.sample_output_dict:
                self._insert_metadata('snpit_species', self.sample_output_dict['snpit']['snpit_species'])
                self._insert_metadata('snpit_lineage', self.sample_output_dict['snpit']['snpit_lineage'])
                self._insert_metadata('snpit_sublineage', self.sample_output_dict['snpit']['snpit_sublineage'])
        elif self.species == 'stec':
            if 'serotype' in self.sample_output_dict:
                # json input
                if 'serotype' in self.sample_output_dict['serotype']:
                    self._insert_metadata('Serotype', self.sample_output_dict['serotype']['serotype'])
                # tsv input
                else:
                    self._insert_metadata('Serotype', self.sample_output_dict['serotype'])
        elif self.species == 'neisseria':
            # tsv input
            if 'detected_serogroup' in self.sample_output_dict:
                self._insert_metadata('Serogroup', self.sample_output_dict['detected_serogroup'])
            # json input
            elif 'serogroup' in self.sample_output_dict:
                self._insert_metadata('Serogroup', self.sample_output_dict['serogroup']['detected_serogroup'])
