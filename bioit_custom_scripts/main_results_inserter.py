import argparse
import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urljoin
import concurrent.futures
import os
import sys
import shutil
import requests
import yaml
import psycopg2
import subprocess
import smtplib
from email.message import EmailMessage
import socket
import traceback

from config import CONFIG
from components.databaseconnection import Database_connection
from components.maininserter import MainInserter
from components.tsv_typingresultsinserter import TypingResultsInserter
from components.tsv_genedetectionresultsinserter import GeneDetectionResultsInserter

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--tsvfilepath', required=True, type=Path)
    argument_parser.add_argument('--isolatename', required=True, type=str)
    argument_parser.add_argument('--uploadermailadress', required=True, type=str)
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    return argument_parser.parse_args()

def send_email(subject: str, content: str, config: dict) -> None:
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

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments()

    # Read the global config
    with open(CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # parse output
    outputtsvdict = {}
    handle = open(args.tsvfilepath, 'r').readlines()
    for line in handle:
        outputtsvdict[line.split('\t')[0]] = line.split('\t')[1].strip('\n')

    #Connect to db and create cursor
    cur_isolates, cur_seqdef = Database_connection().open_database_connections(args.species)

    # Logic
    cur_isolates.execute(f"SELECT COUNT(*) FROM isolates WHERE isolate='{args.isolatename}'")
    sample_presence = cur_isolates.fetchall()
    if sample_presence[0][0] == 0:
        # sample does not exist yet, but check first if any sample exists in insert statement
        cur_isolates.execute(f"INSERT INTO isolates(id, "
                    f"isolate, sender, curator, date_entered, datestamp, uploader)"
                    f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM isolates)+1) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), "
                    f"'{args.isolatename}', 1, 1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), '{args.uploadermailadress}')")
        cur_isolates.execute(f"INSERT INTO history(isolate_id, timestamp, action, curator)"
                    f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{args.isolatename}'),(SELECT NOW()::TIMESTAMP), 'Isolate record added', 1)")
        try:
            MainInserter().insert_main(args.isolatename, args.species, cur_isolates, outputtsvdict)
            TypingResultsInserter().insert_typing_results(args.isolatename, args.species, config_data['species'][args.species]['typing_schemes'], outputtsvdict, cur_isolates, cur_seqdef)
            if config_data['species'][args.species]['genedetection_schemes'] is not None:
                GeneDetectionResultsInserter().insert_genedetection_results(args.isolatename, args.species, config_data['species'][args.species]['genedetection_schemes'], outputtsvdict, cur_isolates, cur_seqdef)
            logging.info('Finished inserting results')
        except Exception as exceptionmessage:
            cur_isolates.execute(f"DELETE FROM isolates WHERE isolate='{args.isolatename}'")
            send_email(
                f'Error inserting output of {args.species} pipeline to bigsdb for sample {args.isolatename} on host {socket.gethostname()}',
                f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])

    elif sample_presence[0][0] == 1:
        # sample exists: check whether typing results or not (we do not bother checking for all schemes separately
        cur_isolates.execute(
            f"SELECT COUNT(*) FROM allele_designations WHERE isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{args.isolatename}')")
        alleles_presence = cur_isolates.fetchall()
        if alleles_presence[0][0] == 0:
            # no allele designations are present so we insert them
            try:
                MainInserter().insert_main(args.isolatename, args.species, cur_isolates, outputtsvdict)
                TypingResultsInserter().insert_typing_results(args.isolatename, args.species, config_data['species'][args.species]['typing_schemes'], outputtsvdict, cur_isolates, cur_seqdef)
                if config_data['species'][args.species]['genedetection_schemes'] is not None:
                    GeneDetectionResultsInserter().insert_genedetection_results(args.isolatename, args.species, config_data['species'][args.species]['genedetection_schemes'], outputtsvdict, cur_isolates, cur_seqdef)
                logging.info('Finished inserting results')
            except Exception as exceptionmessage:
                send_email(
                    f'Error inserting output of {args.species} pipeline to bigsdb for sample {args.isolatename} on host {socket.gethostname()}',
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        elif alleles_presence[0][0] >= 1:
            sys.exit("This sample already contains typing results")

    elif sample_presence[0][0] >= 1:
        # multiple samples with same isolate name are present, that means that there are multiple versions of the same sample
        # check newest version
        cur_isolates.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                    f"isolate_id = (SELECT MAX(id) FROM isolates WHERE isolate='{args.isolatename}')")
        alleles_presence = cur_isolates.fetchall()
        if alleles_presence[0][0] == 0:
            # no allele designations are present so we insert them
            try:
                MainInserter().insert_main(args.isolatename, args.species, cur_isolates, outputtsvdict)
                TypingResultsInserter().insert_typing_results(args.isolatename, args.species, config_data['species'][args.species]['typing_schemes'], outputtsvdict, cur_isolates, cur_seqdef)
                if config_data['species'][args.species]['genedetection_schemes'] is not None:
                    GeneDetectionResultsInserter().insert_genedetection_results(args.isolatename, args.species, config_data['species'][args.species]['genedetection_schemes'], outputtsvdict, cur_isolates, cur_seqdef)
                logging.info('Finished inserting results')
            except Exception as exceptionmessage:
                send_email(
                    f'Error inserting output of {args.species} pipeline to bigsdb for sample {args.isolatename} on host {socket.gethostname()}',
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        elif alleles_presence[0][0] >= 1:
            sys.exit("This sample already contains typing results")
        
        #todo find out if connections need to be closed