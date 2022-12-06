# issue: max(allele_id) != len(allele_id); some alleles are missing in db, need to take count and can not use len!
# But on the other side; allele sequences under Max should not be updated, so i can only start looking from max(db)

# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?


import os
import psycopg2
from pathlib import Path
import shutil
import re
import smtplib
from email.message import EmailMessage
import socket
import traceback
import sys
import logging
import yaml
import argparse

from config import BIGSDB_CONFIG


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
        con_seqdef = psycopg2.connect(database=f"{config_data['species'][species]['seqdefdb']}", user="apache", password="remote",
                               host="127.0.0.1", port="")
        con_seqdef.autocommit = True
        cur_seqdef = con_seqdef.cursor()
        con_isolates = psycopg2.connect(database=f"{config_data['species'][species]['isolatesdb']}", user="apache", password="remote",
                                        host="127.0.0.1", port="")
        con_isolates.autocommit = True
        cur_isolates = con_isolates.cursor()

        schemedict = config_data['species'][species]['typing_schemes']
        for scheme in schemedict.keys():
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
                        cur_seqdef.execute(f"SELECT allele_id FROM sequences WHERE locus='{dir}'")
                        rows = cur_seqdef.fetchall()
                        list_alleleid = []
                        for item in rows:
                            list_alleleid.append(item[0])

                        # Part_3: Compare the two lists
                        ids_to_be_inserted = []
                        if len(list_alleleid):  # not necessary but makes it slightly more elegant for new locus allele sequences
                            for id in list(fastadict.keys()):
                                if id not in list_alleleid:
                                    ids_to_be_inserted.append(id)
                                else:
                                    continue
                        else:
                            ids_to_be_inserted = list(fastadict.keys())
                        print(ids_to_be_inserted)

                        # Part_4: insert missing allele sequences into psql db
                        print(scheme, dir)
                        for id in ids_to_be_inserted:
                            try:
                                """
                                Sometimes alleles retire for seemingly no reason, and are added immediately after as a new allele id,
                                The observed ids that went through this were not in any profile or any allele designation in the isolate db
                                """
                                cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                              VALUES('{dir}','{id}','{fastadict[id]}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                                print(f"id {id} inserted into locus {dir}")
                            except Exception:
                                """
                                Profiles are located in the seqdef db and will automatically update when the sequence db is updated through a rule.
                                Allele designations in the isolate db on the other hand will not, moreover, allele designations in the allele db 
                                do not need to be referring to a real allele in the seqdef db.
                                """
                                cur_seqdef.execute(
                                    f"SELECT allele_id FROM sequences WHERE locus = '{dir}' AND sequence = '{fastadict[id]}'")
                                old_id = cur_seqdef.fetchall()[0][
                                    0]  # If empty then it will be a simple empty list '[]' and taking the index twice will throw an error
                                cur_seqdef.execute(f"UPDATE sequences SET allele_id = '{id}' WHERE locus = '{dir}' AND \
                                              allele_id = '{old_id}'")
                                cur_isolates.execute(
                                    f"UPDATE allele_designations SET allele_id ='{id}' WHERE allele_id ='{old_id}' AND locus = '{dir}'")
        con_seqdef.close()
        cur_isolates.close()


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
    args = _parse_arguments(list(config_data['species'].keys()))

    try:
        _insert_alleles()
    except Exception as exceptionmessage:
        _send_email(
            f'(automated weekly) alleles db update in BIGSdb failed on host {socket.gethostname()}',
            f"{exceptionmessage}\n{traceback.format_exc()}", emaildict)
