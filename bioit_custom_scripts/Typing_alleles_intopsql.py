# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?

import argparse
import logging
import os
import re
import shutil
import smtplib
import socket
import sys
import traceback
from email.message import EmailMessage
from pathlib import Path

import psycopg2
import yaml

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.config import BIGSDB_CONFIG
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


def _insert_alleles() -> None:
    """
    Main function to insert all alleles for the given species
    :return:
    """
    for species in list(set(args.species)):
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        schemedict = config_data['species'][species]['typing_schemes']
        for scheme in schemedict:
            if schemedict[scheme].get('dirdb') and schemedict[scheme]['dirdb'] != '':
                dirs = next(os.walk(schemedict[scheme]['dirdb']))[1]
                for dir in dirs:
                    if not dir.startswith('.') and not (scheme == 'neisseria_fhbpnucl' and (
                            dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (
                            scheme == 'neisseria_fhbppept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
                        # Part 1: Python component
                        # Make dict of fasta file
                        handle = open(
                            Path(schemedict[scheme]['dirdb']) / dir / ''.join([dir.lower(), '.fasta']),
                            'r').readlines()
                        fastadict = {}
                        x = 0
                        if (len(handle) > 2 and not handle[2].startswith(
                                ">")) or scheme == 'neisseria_feta':  # one file had this fasta format where the sequence was on different lines
                            pathcopytempfile = Path('/tmp') / ''.join([dir.lower(), '.fasta'])
                            shutil.copyfile((Path(schemedict[scheme]['dirdb']) / dir / ''.join(
                                [dir.lower(), '.fasta'])), pathcopytempfile)
                            with open(pathcopytempfile, 'r') as file:
                                handle2 = file.read()
                            with open(pathcopytempfile, 'w') as file:
                                file.write(re.sub('(?<=[A-Z])\n(?=[A-Z])', '', handle2))
                            handle = open(pathcopytempfile, 'r').readlines()
                            os.remove(pathcopytempfile)

                        while x < len(handle):
                            if dir == 'rplF' or dir == 'fHbp':
                                fastadict[handle[x].rstrip().replace(f">'{dir}", "").strip("-_")] = handle[x + 1].rstrip()
                                x += 2
                            elif dir == 'fHbp_allele':
                                fastadict[handle[x].rstrip().replace(f">'fHbp", "").strip("-_")] = handle[x + 1].rstrip()
                                x += 2
                            elif dir == 'FetA':
                                fastadict[handle[x].rstrip().replace(f">{dir}_VR", "").strip("-_")] = handle[x + 1].rstrip()
                                x += 2
                            elif dir == 'porB':
                                fastadict[handle[x].rstrip().replace(f">NEIS2020_", "").strip("-_")] = handle[
                                    x + 1].rstrip()
                                x += 2
                            elif dir == 'nhba':
                                fastadict[handle[x].rstrip().replace(f">NEIS2109_", "").strip("-_")] = handle[
                                    x + 1].rstrip()
                                x += 2
                            elif dir == 'nadA':
                                fastadict[handle[x].rstrip().replace(f">NEIS1969_", "").strip("-_")] = handle[
                                    x + 1].rstrip()
                                x += 2
                            else:
                                fastadict[handle[x].rstrip().replace(f">{dir}", "").strip("-_")] = handle[x + 1].rstrip()
                                x += 2

                        # Part 2: PSQL component
                        sqlquery = """SELECT allele_id FROM sequences WHERE locus=%s;"""
                        cur_seqdef.execute(sqlquery, (dir,))
                        rows = cur_seqdef.fetchall()
                        list_alleleid = []
                        for item in rows:
                            list_alleleid.append(item[0])

                        # Part_3: Compare the two lists
                        ids_to_be_inserted = []
                        if len(list_alleleid):  # not necessary but makes it slightly more elegant for new locus allele sequences
                            for id in list(fastadict):
                                if id not in list_alleleid:
                                    ids_to_be_inserted.append(id)
                                else:
                                    continue
                        else:
                            ids_to_be_inserted = list(fastadict)

                        # Part_4: insert missing allele sequences into psql db
                        for id in ids_to_be_inserted:
                            try:
                                """
                                Sometimes alleles retire for seemingly no reason, and are added immediately after as a new allele id,
                                The observed ids that went through this were not in any profile or any allele designation in the isolate db
                                """
                                sqlquery = """
                                           INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                           VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                                cur_seqdef.execute(sqlquery, (dir, fastadict[id]))
                            except Exception:
                                """
                                Profiles are located in the seqdef db and will automatically update when the sequence db is updated through a rule.
                                Allele designations in the isolate db on the other hand will not, moreover, allele designations in the allele db 
                                do not need to be referring to a real allele in the seqdef db.
                                """
                                sqlquery = """SELECT allele_id FROM sequences WHERE locus=%s AND sequence=%s;"""
                                cur_seqdef.execute(sqlquery, (dir, fastadict[id]))
                                old_id = cur_seqdef.fetchall()[0][
                                    0]  # If empty then it will be a simple empty list '[]' and taking the index twice will throw an error
                                sqlquery = """UPDATE sequences SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""
                                cur_seqdef.execute(sqlquery, (id, dir, old_id))
                                sqlquery = """UPDATE allele_designations SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""
                                cur_isolates.execute(sqlquery, (id, dir, old_id))
        DatabaseConnection().close_connections(con_isolates, con_seqdef)


def _send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :param config: Config containing the maildict
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
    args = _parse_arguments(list(config_data['species']))

    try:
        _insert_alleles()
    except Exception as exceptionmessage:
        _send_email(
            f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
            f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
        raise Exception(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}")
