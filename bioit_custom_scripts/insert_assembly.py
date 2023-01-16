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
    argument_parser.add_argument('--fastafilepath', required=True, type=str)
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    argument_parser.add_argument('--isolatename', required=True, type=str)
    return argument_parser.parse_args()

def _send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
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
    
def insert_assembly(isolatename: str, species: str, fastafilepath: str) -> None:
    # Read the global config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    try:
        # Connect to db and create cursors
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        sqlquery = """SELECT COUNT(*) FROM isolates WHERE isolate=%s;"""
        cur_isolates.execute(sqlquery, (isolatename,))
        sample_presence = cur_isolates.fetchall()
        if sample_presence[0][0] == 0:
            _send_email(
                f'{os.path.basename(__file__)}: Error inserting assembly of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.',
                f"please insert isolate/isolate results first", config_data['mail'])
            sys.exit()

        sqlquery = """SELECT count(*) FROM sequence_bin WHERE isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate=%s);"""
        cur_isolates.execute(sqlquery, (isolatename,))
        presentcontigs = cur_isolates.fetchall()
        if presentcontigs[0][0] == 0:
            # Make dict of fasta file while accounting for possible multiline sequences
            handle = open(Path(fastafilepath), 'r').readlines()
            fastadict = {}
            x = 0
            if len(handle) > 2 and not handle[2].startswith(
                    ">"):  # one file had this fasta format where the sequence was on different lines
                pathcopytempfile = Path('/tmp') / ''.join([isolatename.lower(), '.fasta'])
                shutil.copyfile((Path(fastafilepath)), pathcopytempfile)
                with open(pathcopytempfile, 'r') as file:
                    handle2 = file.read()
                with open(pathcopytempfile, 'w') as file:
                    file.write(re.sub('(?<=[A-Z])\n(?=[A-Z])', '', handle2))
                handle = open(pathcopytempfile, 'r').readlines()
                os.remove(pathcopytempfile)

            while x < len(handle):
                if handle[x].startswith(">"):
                    fastadict[handle[x].rstrip().replace(f">{isolatename}", "").strip("-_")] = handle[x + 1].rstrip()
                x += 2

            # insert into database
            for sequencename, sequence in fastadict.items():
                sqlquery = """
                           INSERT INTO sequence_bin(id, 
                           isolate_id, 
                           remote_contig, sequence, original_designation, sender, 
                           curator, date_entered, datestamp) 
                           VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM sequence_bin) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM sequence_bin)+1) END), 
                           (SELECT MAX(id) FROM isolates WHERE isolate=%s), 
                           'f', %s, %s, 1, 
                           1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))"""
                cur_isolates.execute(sqlquery, (isolatename, sequence,sequencename.strip('>')))
            # # remove the file
            # os.remove(Path(fastafile))

        else:
            _send_email(
                f'{os.path.basename(__file__)}: Error inserting assembly of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.',
                f"isolate {isolatename} already contains assembly records!", config_data['mail'])
            sys.exit()

        DatabaseConnection().close_connections(con_isolates, con_seqdef)
    except Exception as exceptionmessage:
        _send_email(
            f'{os.path.basename(__file__)}: Error inserting assembly of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.',
            f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        sys.exit()


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Read the global config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(list(config_data['species'].keys()))

    # run main
    insert_assembly(args.isolatename, args.species, args.fastafilepath)
