import logging

from .json_superclass import JsonSuperClass

class MainInserter(JsonSuperClass):
    """
    Class containing all queries for Mongo
    """

    def __init__(self, isolatename, species, cur_isolates, cur_seqdef, outputtsvdict):
        JsonSuperClass.__init__(self, isolatename, species, cur_isolates, cur_seqdef, outputtsvdict)
        # discrepancy between tsv and json
        self.outputtsvdict = self.outputjsondict

    def insert_main(self):
        reportlink = f'<p><a href="/galaxyreports/{self.species}/{self.isolatename}/report.html" target="_blank"> html report</a></p>'
        self._insert_metadata('html', reportlink)
        self._insert_metadata('tsv', reportlink.replace('html', 'tsv'))
        self._insert_species_specific()
        logging.info('Metadata insertion succesful')
    
    def _insert_species_specific(self):
        if self.species == 'mycobacterium':
            # tsv input
            if '51SNP-gyrB_group' in self.outputtsvdict:
                self._insert_metadata('gyrB_group', self.outputtsvdict['51SNP-gyrB_group'])
                self._insert_metadata('Genetic_group', self.outputtsvdict['51SNP-genetic_group'])
                self._insert_metadata('SCG', self.outputtsvdict['51SNP-scg'])
            # json input
            elif '51SNP' in self.outputtsvdict:
                self._insert_metadata('gyrB_group', self.outputtsvdict['51SNP']['51SNP-gyrB_group'])
                self._insert_metadata('Genetic_group', self.outputtsvdict['51SNP']['51SNP-genetic_group'])
                self._insert_metadata('SCG', self.outputtsvdict['51SNP']['51SNP-scg'])
            # tsv input
            if 'snpit_species' in self.outputtsvdict:
                self._insert_metadata('snpit_species', self.outputtsvdict['snpit_species'])
                self._insert_metadata('snpit_lineage', self.outputtsvdict['snpit_lineage'])
                self._insert_metadata('snpit_sublineage', self.outputtsvdict['snpit_sublineage'])
            # json input
            elif 'snpit' in self.outputtsvdict:
                self._insert_metadata('snpit_species', self.outputtsvdict['snpit']['snpit_species'])
                self._insert_metadata('snpit_lineage', self.outputtsvdict['snpit']['snpit_lineage'])
                self._insert_metadata('snpit_sublineage', self.outputtsvdict['snpit']['snpit_sublineage'])
        elif self.species == 'stec':
            if 'serotype' in self.outputtsvdict:
                # json input
                if 'serotype' in self.outputtsvdict['serotype']:
                    self._insert_metadata('Serotype', self.outputtsvdict['serotype']['serotype'])
                # tsv input
                else:
                    self._insert_metadata('Serotype', self.outputtsvdict['serotype'])
        elif self.species == 'neisseria':
            # tsv input
            if 'detected_serogroup' in self.outputtsvdict:
                self._insert_metadata('Serogroup', self.outputtsvdict['detected_serogroup'])
            # json input
            elif 'serogroup' in self.outputtsvdict:
                self._insert_metadata('Serogroup', self.outputtsvdict['serogroup']['detected_serogroup'])
