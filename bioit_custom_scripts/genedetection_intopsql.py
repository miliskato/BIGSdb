import argparse
import json
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from bioit_custom_scripts.components.json_superclass import JsonSuperClass
from bioit_custom_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email

def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=specieslist, default=specieslist,
                                 nargs='+')  # this does allow for the same species multiple times but doesnt really matter
    return argument_parser.parse_args()

class GeneDetectionIntoPsql:
    """
    Class containing function to insert gene detection loci and alleles and update them (weekly)
    """

    def __init__(self, bigsdb_config_data: Dict[str, Any], species: str) -> None:
        self.bigsdb_config_data = bigsdb_config_data
        self.species = species
        (self.con_isolates, self.cur_isolates), (self.con_seqdef, self.cur_seqdef) \
            = DatabaseConnection().connect_to_dbs_and_create_cursors(self.species)
        self._schemedict: Dict[str, Any] = self.bigsdb_config_data['species'][self.species]['genedetection_schemes']
        self.gene_detection_insertion_and_recalcultation()
        DatabaseConnection().close_connections(self.con_isolates, self.con_seqdef)
        
    def gene_detection_insertion_and_recalcultation(self) -> None:
        """
        Inserts gene detection loci and alleles and recalculates existing loci/alleles
        Recalculation pertains the Clusters which are recalculated weekly on often 80% identity
        :return: None
        """
        if self._schemedict is not None:
            for scheme in self._schemedict:
                self._scheme: str = scheme

                self._create_necessary_dictionaries()

                self._insert_loci_and_alleles()

                self._update_locus_descriptions()

                self._recalculate_allele_designations()

    def _create_necessary_dictionaries(self) -> None:
        """
        Creates the necessary dictionaries of the current database version
        :return: None
        """
        self.descriptiondict: Dict[str, List[str]] = {}  # e.g. 'VFDB_GeneCluster_0' : ['gene1', 'gene2']
        self.clusterdict: Dict[str, str] = {}  # e.g. 'accesion1_allele1': 'VFDB_GeneCluster_0'
        with Path(self._schemedict[self._scheme]['metadatafile']).open('r') as handle:
            sequencedictlist: Dict[str, Dict[Any]] = json.load(handle)
            for sequencename in sequencedictlist:
                """
                sequencename becomes accession concatenated with allele because in e.g. 
                Resfinder, multiple accessions are not unique.
                sequencefile looks like this: 
                {'seq_0': {'accession': 'NG_047553.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 
                           'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 
                           'header_orig': 'NG_047553.1_1567214_ble', 'cluster': 'Cluster_881'}, 
                 'seq_1': {'accession': 'NG_047554.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 
                           'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 
                           'header_orig': 'NG_047554.1_1567214_ble', 'cluster': 'Cluster_881'}, 
                 'seq_2': {'accession': 'NG_056058.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 
                           'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 
                           'header_orig': 'NG_056058.1_BcII', 'cluster': 'Cluster_561'}, 
                 'seq_3': {'accession': 'NG_047221.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 
                           'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 
                           'header_orig': 'NG_047221.1_BcII', 'cluster': 'Cluster_561'}}
                """
                if sequencedictlist[sequencename]['accession'] is None:
                    sequencedictlist[sequencename]['accession'] = "-"
                geneclusternamebigsdb: str = f"{self._schemedict[self._scheme]['schemename_bigsdb']}_Gene{sequencedictlist[sequencename]['cluster']}"
                self.clusterdict['_'.join([(sequencedictlist[sequencename]['accession']),
                                           (sequencedictlist[sequencename]['allele']).replace("'", "")])] = geneclusternamebigsdb
                if not self.descriptiondict.get(geneclusternamebigsdb):
                    self.descriptiondict[geneclusternamebigsdb] = []
                if self._schemedict[self._scheme]['schemename_bigsdb'] != 'VFDB_core':
                    self.descriptiondict[geneclusternamebigsdb].append(
                        (sequencedictlist[sequencename]['allele']).replace("'", ""))
                else:
                    self.descriptiondict[geneclusternamebigsdb].append(
                        (sequencedictlist[sequencename]['gene']).replace("'", ""))
        self.clusterlist: List[str] = self.descriptiondict.keys()

    def _insert_loci_and_alleles(self) -> None:
        """
        Inserts all the loci (clusters), scheme members and alleles (dummy boolean) in seqdef and isolate dbs if they are not present
        :return: None
        """
        json_superclass_instance = JsonSuperClass('dummyname', self.species, self.cur_isolates, self.cur_seqdef,
                                                  {'dummydictkey': 'dummydictvalue'})
        for cluster in self.clusterlist:
            sqlquery = """SELECT COUNT(*) FROM loci WHERE id=%s"""
            self.cur_seqdef.execute(sqlquery, (cluster,))
            present = self.cur_seqdef.fetchall()
            if present[0][0] == 0:
                json_superclass_instance._insert_locus_if_needed(cluster, self._schemedict[self._scheme]['schemename_bigsdb'])
                sqlquery = """
                           INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) 
                           VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                self.cur_seqdef.execute(sqlquery, (cluster, 1, 'TAG'))
                self.cur_seqdef.execute(sqlquery, (cluster, 0, 'null allele'))
            else:
                continue

    def _update_locus_descriptions(self) -> None:
        """
        Updates the locus descriptions to the new database version
        :return: None
        """
        sqlquery = """DELETE FROM locus_descriptions WHERE locus LIKE %s;"""
        self.cur_seqdef.execute(sqlquery, (f"{self._schemedict[self._scheme]['schemename_bigsdb']}_GeneCluster%",))
        for cluster, description in self.descriptiondict.items():
            # convert list to more meaningfull and aesthatically pleasing string
            descriptionstring = ' '.join(['Contains genes:', ', '.join([x for x in description])])
            sqlquery = """
                       INSERT INTO locus_descriptions(locus, product, description, datestamp, curator) 
                       VALUES(%s, %s, %s ,(SELECT CURRENT_DATE), 1);"""
            self.cur_seqdef.execute(sqlquery,
                                    (cluster, descriptionstring.replace('Contains genes:', ''), descriptionstring))

    def _recalculate_allele_designations(self) -> None:
        """
        Removes, recaculates and reinserts allele designations
        :return: None
        """
        sqlquery = """DELETE FROM allele_designations WHERE locus LIKE %s;"""
        self.cur_isolates.execute(sqlquery, (f"{self._schemedict[self._scheme]['schemename_bigsdb']}_GeneCluster%",))
        sqlquery = """
                                   SELECT eav_text_hidden.isolate_id, eav_text_hidden.value, isolates.isolate FROM eav_text_hidden 
                                   LEFT JOIN isolates ON isolates.id = eav_text_hidden.isolate_id WHERE eav_text_hidden.field=%s;"""
        self.cur_isolates.execute(sqlquery, (self._schemedict[self._scheme]['schemename_bigsdb'],))
        listofsamplesandhits = self.cur_isolates.fetchall()
        if len(listofsamplesandhits) != 0:
           for sampleandhits in listofsamplesandhits:
                isolate_id: str = sampleandhits[0]
                isolate_name: str = sampleandhits[2]
                eavhtmltable: str = '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                clusterhitset: set = set()  # in case loci that were in different clusters at some point get in the same cluster
                hits = json.loads(sampleandhits[1])
                if len(hits) != 0:
                    for y in range(len(hits)):
                        if isinstance(hits[y], list):
                            # allele is always position 1 and accession is always last position (-1)
                            hit: str = '_'.join([(hits)[y][-1],
                                            (hits)[y][1]])
                            clusterhit: str = self.clusterdict[hit]
                            # append Cluster
                            eavhtmltable: str = eavhtmltable + ''.join(
                                ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                            # append Locus
                            index: int = -2 if self._scheme == 'vfdb_core' else 1
                            eavhtmltable: str = eavhtmltable + ''.join(
                                ['<td><a href="/galaxyreports/', self.species, '/', isolate_name,
                                 '/report.html#', self._schemedict[self._scheme]['schemename_html'],
                                 '" target="_blank">',
                                 (hits)[y][index], '</a></td></tr>'])

                        elif isinstance(hits[y], dict):
                            hit: str = '_'.join([(hits)[y]['Accession'],
                                            (hits)[y]['Locus']])
                            clusterhit: str = self.clusterdict[hit]
                            # append Cluster
                            eavhtmltable: str = eavhtmltable + ''.join(
                                ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                            # append Locus
                            htmlname: str = 'Gene' if self._scheme == 'vfdb_core' else 'Locus'
                            eavhtmltable: str = eavhtmltable + ''.join(
                                ['<td><a href="/galaxyreports/', self.species, '/', isolate_name,
                                 '/report.html#', self._schemedict[self._scheme]['schemename_html'],
                                 '" target="_blank">',
                                 (hits)[y][htmlname], '</a></td></tr>'])

                        if clusterhit not in clusterhitset:
                            sqlquery = """
                                                       INSERT INTO allele_designations(locus, isolate_id, 
                                                       allele_id, status, method, sender, 
                                                       curator, date_entered, datestamp) 
                                                       VALUES(%s, %s, 
                                                       %s, 'confirmed', 'automatic', 1, 
                                                       1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
                            self.cur_isolates.execute(sqlquery, (clusterhit, isolate_id, 1))
                            clusterhitset.add(clusterhit)
                    eavhtmltable: str = eavhtmltable + '</table>'
                    sqlquery = """DELETE FROM eav_text WHERE isolate_id=%s AND field=%s;"""
                    self.cur_isolates.execute(sqlquery, (isolate_id, self._schemedict[self._scheme]['schemename_bigsdb']))
                    sqlquery = """INSERT INTO eav_text(isolate_id, field, value) VALUES(%s, %s, %s);"""
                    self.cur_isolates.execute(sqlquery, (isolate_id, self._schemedict[self._scheme]['schemename_bigsdb'], eavhtmltable))
                    sqlquery = """
                                               INSERT INTO history(isolate_id, timestamp, action, curator) 
                                               VALUES(%s, (SELECT NOW()::TIMESTAMP), 'Gene detection results reevaluated after database update', 1);"""
                    self.cur_isolates.execute(sqlquery, (isolate_id,))


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    try:
        for species in set(args.species):
            GeneDetectionIntoPsql(bigsdb_config_data, species)
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")
