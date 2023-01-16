# I will not create schemes, these have to be created by the users manually
# I will create loci/clusters in both both the seqdef and the isolate db and also put these loci/clusters
# into schemes and link the loci/clusters from isolate db to seqdef db
# I will also fill up these clusters with dummy alleles being TAG (allele id 1) and null allele (allele id 0) although null allele is not necessarily neccesary

import os
import psycopg2
from pathlib import Path
import json
import smtplib
from email.message import EmailMessage
import socket
import traceback
import sys
import logging
import yaml
import argparse

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.config import BIGSDB_CONFIG
from bioit_custom_scripts.components.json_superclass import JsonSuperClass
from bioit_custom_scripts.components.databaseconnection import DatabaseConnection


def _parse_arguments(specieslist: list) -> argparse.Namespace:
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


def _gene_detection_insertion_recalcultation():
    for species in list(set(args.species)):
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        schemedict = config_data['species'][species]['genedetection_schemes']
        if schemedict is not None:
            for scheme in schemedict.keys():
                # Part 1 adding all the loci (clusters), scheme members and alleles (dummy boolean) in seqdef and isolate dbs
                clusterfile = open(Path(schemedict[scheme]['clusteredfasta']), 'r').readlines()
                clusterlist = []
                for line in clusterfile:
                    # line looks like this: >0__Cluster_0__seq_4648__seq_4648
                    if line.startswith('>'):
                        clusterlist.append('_'.join([schemedict[scheme]['schemename_bigsdb'], ''.join(['Gene', line.split('__')[1]])]))
                json_superclass_instance = JsonSuperClass('dummyname', species, cur_isolates, cur_seqdef, {'dummydictkey': 'dummydictvalue'})
                for cluster in clusterlist:
                    cur_seqdef.execute(f"SELECT count(*) FROM loci WHERE id='{cluster}'")
                    present = cur_seqdef.fetchall()
                    if present[0][0] == 0:
                        json_superclass_instance._insert_locus_if_needed(cluster, schemedict[scheme]['schemename_bigsdb'])
                        sqlquery = """
                                   INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) 
                                   VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                        cur_seqdef.execute(sqlquery, (cluster, 1, 'TAG'))
                        cur_seqdef.execute(sqlquery, (cluster, 0, 'null allele'))
                    else:
                        continue

                #Part 2 removing and updating all allele designations (clusters) for all isolates containing data for that gene detection cluster.

                # initiate Cluster dict with description (= genes) in list format by creating empty lists
                descriptiondict = {}
                for cluster in clusterlist:
                    descriptiondict[cluster] = []

                # first create a cluster content list
                sequencefile = json.load(open(Path(schemedict[scheme]['metadatafile']), 'r'))
                sequencenamedict = {}
                for x in list(sequencefile):
                    # sequencename becomes accession concatenated with allele because in e.g. Resfinder, multiple accessions are not unique. Also allele is in every mapping_full.json, but not gene
                    # sequencefile looks like this: {'seq_0': {'accession': 'NG_047553.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047553.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_1': {'accession': 'NG_047554.1', 'antibiotic': 'Bleomycin', 'allele': '1567214_ble', 'gene': '1567214_ble', 'product': 'BLMA family bleomycin binding protein', 'header_orig': 'NG_047554.1_1567214_ble', 'cluster': 'Cluster_881'}, 'seq_2': {'accession': 'NG_056058.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_056058.1_BcII', 'cluster': 'Cluster_561'}, 'seq_3': {'accession': 'NG_047221.1', 'antibiotic': 'Carbapenem', 'allele': 'BcII', 'gene': 'BcII', 'product': 'BcII family subclass B1 metallo-beta-lactamase', 'header_orig': 'NG_047221.1_BcII', 'cluster': 'Cluster_561'}}
                    # in VFDB, there are accessions with name "null", this breaks the script, therefore an empty space is added, and the allele should be enough to find.
                    if sequencefile[x]['accession'] is None:
                        sequencefile[x]['accession'] = "-"
                    sequencenamedict[x] = '_'.join([(sequencefile[x]['accession']), (sequencefile[x]['allele']).replace("'", "")])
                    if schemedict[scheme]['schemename_bigsdb'] != 'VFDB_core':
                        descriptiondict['_'.join([schemedict[scheme]['schemename_bigsdb'], (''.join(['Gene', sequencefile[x]['cluster']]))])].append((sequencefile[x]['allele']).replace("'", ""))
                    else:
                        descriptiondict['_'.join([schemedict[scheme]['schemename_bigsdb'], (''.join(['Gene', sequencefile[x]['cluster']]))])].append((sequencefile[x]['gene']).replace("'", ""))
                clusterfile = open(Path(schemedict[scheme]['clusteredfasta']), 'r').readlines()
                clusterdict = {}
                for line in clusterfile:
                    # line looks like this: >0__Cluster_0__seq_4648__seq_4648
                    if line.startswith('>'):
                        # key is sequencename from previous dict, value is cluster
                        clusterdict[sequencenamedict[line.split('__')[2]]] = '_'.join([schemedict[scheme]['schemename_bigsdb'], ''.join(['Gene', line.split('__')[1]])])
                        # e.g. sequencenamedict['NG_047553.11567214_ble'] = 'GeneCluster_0'

                # set the descriptions of the loci, comma separated list of all genes
                sqlquery = """DELETE FROM locus_descriptions WHERE locus LIKE %s;"""
                cur_seqdef.execute(sqlquery, (f"{schemedict[scheme]['schemename_bigsdb']}_GeneCluster%",))
                for cluster, description in descriptiondict.items():
                    # convert list to more meaningfull and aesthatically pleasing string
                    descriptionstring = ' '.join(['Contains genes:', ', '.join([x for x in description])])
                    sqlquery = """
                               INSERT INTO locus_descriptions(locus, product, description, datestamp, curator) 
                               VALUES(%s, %s, %s ,(SELECT CURRENT_DATE), 1);"""
                    cur_seqdef.execute(sqlquery, (cluster, descriptionstring.replace('Contains genes:',''), descriptionstring))
                sqlquery = """DELETE FROM allele_designations WHERE locus LIKE %s;"""
                cur_isolates.execute(sqlquery, (f"{schemedict[scheme]['schemename_bigsdb']}_GeneCluster%",))
                sqlquery = """
                           SELECT eav_text_hidden.isolate_id, eav_text_hidden.value, isolates.isolate FROM eav_text_hidden 
                           LEFT JOIN isolates ON isolates.id = eav_text_hidden.isolate_id WHERE eav_text_hidden.field=%s;"""
                cur_isolates.execute(sqlquery, (schemedict[scheme]['schemename_bigsdb'],))
                listofsamplesandhits = cur_isolates.fetchall()
                # this might look something like this currently: [(3, '[["Cluster_15", "ActA_1", "94.20", "1915/1920", "NODE_24_length_29899_cov_7.347474", "26015..27929", "NC_003210.1"], ["Cluster_59", "AgrA_1", "98.90", "729/729", "NODE_2_length_347775_cov_7.239843", "324619..325347", "NC_003210.1"], ["Cluster_67", "clpp_1", "96.82", "597/597", "NODE_5_length_187626_cov_7.284412", "124253..124849", "NC_003210.1"], ["Cluster_55", "codY_1", "95.26", "780/780", "NODE_14_length_77047_cov_5.065224", "15699..16478", "NC_003210.1"], ["Cluster_28", "ctaP_1", "97.91", "1575/1575", "NODE_8_length_111969_cov_7.509254", "4180..5754", "NC_003210.1"], ["Cluster_72", "ctsR_1", "96.95", "459/459", "NODE_3_length_239115_cov_6.610227", "396..854", "NC_003210.1"], ["Cluster_40", "dal_1", "92.32", "1107/1107", "NODE_13_length_82610_cov_5.507547", "35258..36364", "NC_003210.1"], ["Cluster_61", "degU_1", "98.84", "687/687", "NODE_5_length_187626_cov_7.284412", "72335..73021", "NC_003210.1"], ["Cluster_29", "dltA_1", "96.02", "1533/1533", "NODE_18_length_59308_cov_5.458390", "50475..52007", "NC_003210.1"]]'), (4, '["Cluster_0", "Eut_operon_1", "97.06", "15039/15038", "NODE_9_length_109885_cov_5.345642", "68077..83115", "NC_003210.1"], ["Cluster_23", "fbpA_1", "91.71", "1713/1713", "NODE_1_length_368586_cov_5.801544", "317694..319406", "NC_003210.1"], ["Cluster_53", "FlaA_1", "98.15", "864/864", "NODE_16_length_63978_cov_5.528441", "47023..47886", "NC_003210.1"], ["Cluster_38", "FlgE_1", "94.01", "1236/1236", "NODE_16_length_63978_cov_5.528441", "41031..42266", "NC_003210.1"], ["Cluster_76", "FlgC_1", "92.46", "411/411", "NODE_16_length_63978_cov_5.528441", "29381..29791", "NC_003210.1"], ["Cluster_70", "fri_1", "97.86", "467/471", "NODE_27_length_26080_cov_5.738643", "7405..7871", "NC_003210.1"], ["Cluster_73", "fur_1", "96.25", "453/453", "NODE_1_length_368586_cov_5.801544", "184454..184906", "NC_003210.1"], ["Cluster_16", "Gmar_1", "96.97", "1914/1914", "NODE_16_length_63978_cov_5.528441", "49045..50958", "NC_017537.1"], ["Cluster_79", "hfq_1", "99.14", "234/234", "NODE_14_length_77047_cov_5.065224", "32920..33153", "NC_003210.1"]')]
                x = 0
                if len(listofsamplesandhits) != 0:
                    while x <= (len(listofsamplesandhits) - 1):
                        isolate_id = listofsamplesandhits[x][0]
                        isolate_name = listofsamplesandhits[x][2]
                        eavhtmltable = '<table class="data"><tr><th>GeneCluster</th><th>Locus</th></tr>'
                        clusterhitlist = []  # in case loci that were in different clusters at some point get in the same cluster
                        if json.loads(listofsamplesandhits[x][1]) != []:
                            for y in range(len(json.loads(listofsamplesandhits[x][1]))):
                                if isinstance(json.loads(listofsamplesandhits[x][1])[y], list):
                                    # allele is always position 1 and accession is always last position (-1)
                                    hit = '_'.join([(json.loads(listofsamplesandhits[x][1]))[y][-1], (json.loads(listofsamplesandhits[x][1]))[y][1]])
                                    clusterhit = clusterdict[hit]
                                    # append Cluster
                                    eavhtmltable = eavhtmltable + ''.join(
                                        ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                                    # append Locus
                                    if scheme != 'vfdb_core':
                                        eavhtmltable = eavhtmltable + ''.join(
                                            ['<td><a href="/galaxyreports/', species, '/', isolate_name,
                                             '/report.html#', schemedict[scheme]['schemename_html'], '" target="_blank">',
                                             (json.loads(listofsamplesandhits[x][1]))[y][1], '</a></td></tr>'])
                                    else:
                                        eavhtmltable = eavhtmltable + ''.join(
                                            ['<td><a href="/galaxyreports/', species, '/', isolate_name,
                                             '/report.html#', schemedict[scheme]['schemename_html'], '" target="_blank">',
                                             (json.loads(listofsamplesandhits[x][1]))[y][-2], '</a></td></tr>'])

                                elif isinstance(json.loads(listofsamplesandhits[x][1])[y], dict):
                                    hit = '_'.join([(json.loads(listofsamplesandhits[x][1]))[y]['Accession'],
                                                    (json.loads(listofsamplesandhits[x][1]))[y]['Locus']])
                                    clusterhit = clusterdict[hit]
                                    # append Cluster
                                    eavhtmltable = eavhtmltable + ''.join(
                                        ['<tr><td>', ''.join(['GeneCluster', clusterhit.split('Cluster')[1]]), '</td>'])
                                    # append Locus
                                    if scheme != 'vfdb_core':
                                        eavhtmltable = eavhtmltable + ''.join(
                                            ['<td><a href="/galaxyreports/', species, '/', isolate_name,
                                             '/report.html#', schemedict[scheme]['schemename_html'], '" target="_blank">',
                                             (json.loads(listofsamplesandhits[x][1]))[y]['Locus'], '</a></td></tr>'])
                                    else:
                                        eavhtmltable = eavhtmltable + ''.join(
                                            ['<td><a href="/galaxyreports/', species, '/', isolate_name,
                                             '/report.html#', schemedict[scheme]['schemename_html'], '" target="_blank">',
                                             (json.loads(listofsamplesandhits[x][1]))[y]['Gene'], '</a></td></tr>'])

                                if clusterhit not in clusterhitlist:
                                    sqlquery = """
                                               INSERT INTO allele_designations(locus, isolate_id, 
                                               allele_id, status, method, sender, 
                                               curator, date_entered, datestamp) 
                                               VALUES(%s, %s, 
                                               %s, 'confirmed', 'automatic', 1, 
                                               1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
                                    cur_isolates.execute(sqlquery, (clusterhit, isolate_id, 1))
                                    clusterhitlist.append(clusterhit)
                            eavhtmltable = eavhtmltable + '</table>'
                            sqlquery = """DELETE FROM eav_text WHERE isolate_id=%s AND field=%s;"""
                            cur_isolates.execute(sqlquery, (isolate_id, schemedict[scheme]['schemename_bigsdb']))
                            sqlquery = """INSERT INTO eav_text(isolate_id, field, value) VALUES(%s, %s, %s);"""
                            cur_isolates.execute(sqlquery, (isolate_id, schemedict[scheme]['schemename_bigsdb'], eavhtmltable))
                            x += 1
                            sqlquery = """
                                       INSERT INTO history(isolate_id, timestamp, action, curator) 
                                       VALUES(%s, (SELECT NOW()::TIMESTAMP), 'Gene detection results reevaluated after database update', 1);"""
                            cur_isolates.execute(sqlquery, (isolate_id,))
        DatabaseConnection().close_connections(con_isolates, con_seqdef)


def _send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :param config: config containing mail dict
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)
    logging.info(content)

if __name__ == '__main__':

    # Read the global config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)
    emaildict = config_data['mail']

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(config_data['species'].keys()))

    try:
        _gene_detection_insertion_recalcultation()
    except Exception as exceptionmessage:
        _send_email(
            f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
            f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
        raise Exception(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}")
