import argparse
import json
import logging
from pathlib import Path
import sys
import yaml
import smtplib
from email.message import EmailMessage
import socket
import traceback
import os
import datetime

from config import BIGSDB_CONFIG
from components.databaseconnection import Database_connection
from components.maininserter import MainInserter
from components.tsv_typingresultsinserter import TsvTypingResultsInserter
from components.tsv_genedetectionresultsinserter import TsvGeneDetectionResultsInserter
from components.json_typingresultsinserter import JsonTypingResultsInserter
from components.json_genedetectionresultsinserter import JsonGeneDetectionResultsInserter

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    mutually_exclusive_group = argument_parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--tsvfilepath', type=Path)
    mutually_exclusive_group.add_argument('--jsonfilepath', type=Path)
    argument_parser.add_argument('--isolatename', required=True, type=str)
    argument_parser.add_argument('--uploadermailadress', required=True, type=str)
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    argument_parser.add_argument("--results_type", required=True, type=str, choices=['new_isolate', 'reanalysis'])
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

def __make_flagfilepath(isolatename: str, config: dict):
    return Path(config['failsafe']['flag_dir']) / '.'.join([isolatename, config['failsafe']['flag_append']])

def _fail_safe_mechanism(isolatename: str, species: str, config: dict, analysis_date: str):
    try:
        if not os.path.isdir(Path(config['failsafe']['flag_dir'])):
            os.makedirs(Path(config['failsafe']['flag_dir']), exist_ok=True)
        flagfilepath = __make_flagfilepath(isolatename, config)
        if os.path.isfile(flagfilepath):
            logging.warning(f"fail safe mechanism detects that the bigsdb insertion for sample {isolatename} was started but didnt finish. Removing {isolatename} from Bigsdb to be able to restart inserting.")
            cur_isolates, cur_seqdef = Database_connection().open_database_connections(species)
            cur_isolates.execute(f"SELECT COUNT(*) FROM isolates WHERE isolate='{isolatename}'")
            nr_of_versions = cur_isolates.fetchall()[0][0]
            cur_isolates.execute(f"DELETE FROM isolates WHERE isolate='{isolatename}' AND id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}') ")
            if nr_of_versions > 1:
                cur_isolates.execute(
                            f"INSERT INTO isolates(id, isolate, sender, curator, date_entered, datestamp, uploader, latest_analyis_date) "
                            f"VALUES((SELECT CASE WHEN (SELECT(SELECT MAX(id) FROM isolates)+1) IS NULL THEN 1 "
                            f"ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), '{isolatename}', 1, 1, "
                            f"(SELECT CURRENT_DATE),(SELECT CURRENT_DATE), "
                            f"(SELECT uploader FROM isolates WHERE isolate='{isolatename}' AND id=(SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}')),"
                            f"'{datetime.datetime.strptime(analysis_date, '%d/%m/%Y - %X').strftime('%Y-%m-%d')}')")
                cur_isolates.execute(
                    f"UPDATE isolates SET new_version=(SELECT MAX(id) FROM isolates WHERE isolate='{isolatename}') "
                    f"WHERE isolate='{isolatename}' AND new_version IS NULL AND id!=(SELECT MAX(id) "
                    f"FROM isolates WHERE isolate='{isolatename}')")
        else:
            flagfilepath.touch()
            logging.info(f"flagfilepath {flagfilepath}")
    except Exception as exceptionmessage:
        _send_email(f"bigsdb upload fail safe mechanism fail on host {socket.gethostname()}", f"{exceptionmessage}\n{traceback.format_exc()}", config['mail'])

def _delete_flagfile(isolatename: str, config: dict):
    flagfilepath = __make_flagfilepath(isolatename, config)
    try:
        os.remove(flagfilepath)
    except Exception as exceptionmessage:
        _send_email(f"Could not remove flag file {flagfilepath} on host {socket.gethostname()}", f"{exceptionmessage}\n{traceback.format_exc()}", config['mail'])

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments()

    # Read the global config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # parse output
    if args.tsvfilepath:
        sample_output_dict = {}
        handle = open(args.tsvfilepath, 'r').readlines()
        for line in handle:
            sample_output_dict[line.split('\t')[0]] = line.split('\t')[1].strip('\n')
    elif args.jsonfilepath:
        records = json.load(open(args.jsonfilepath, 'r'))
        if 'results' in records.keys():
            # records come from mongodb
            sample_output_dict = records['results']
        else:
            # records come from the pipeline directly
            sample_output_dict = records

    #Connect to db and create cursor
    cur_isolates, cur_seqdef = Database_connection().open_database_connections(args.species)
    # Logic
    try:
        maininserter = MainInserter(args.isolatename, args.species, cur_isolates, cur_seqdef, sample_output_dict)
        _fail_safe_mechanism(args.isolatename, args.species, config_data, sample_output_dict['analysis_date'])
        if args.results_type == 'new_isolate':
            maininserter.insert_new_isolate(args.uploadermailadress)
        elif args.results_type == 'reanalysis':
            maininserter.insert_new_isolate_version()
        try:
            maininserter.insert_main_metadata()
            if args.tsvfilepath:
                TsvTypingResultsInserter().insert_typing_results(args.isolatename, args.species, config_data['species'][args.species]['typing_schemes'], sample_output_dict, cur_isolates, cur_seqdef)
                TsvGeneDetectionResultsInserter().insert_genedetection_results(args.isolatename, args.species, config_data['species'][args.species]['genedetection_schemes'], sample_output_dict, cur_isolates, cur_seqdef)
            elif args.jsonfilepath:
                JsonTypingResultsInserter(args.isolatename, args.species, cur_isolates, cur_seqdef, sample_output_dict).insert_typing_results(config_data['species_json'][args.species]['typing_schemes'])
                JsonGeneDetectionResultsInserter(args.isolatename, args.species, cur_isolates, cur_seqdef, sample_output_dict).insert_genedetection_results(config_data['species_json'][args.species]['genedetection_schemes'])
            logging.info('Finished inserting results')
        except Exception as exceptionmessage:
            _send_email(
                f'Error inserting output of {args.species} pipeline to bigsdb for sample {args.isolatename} on host {socket.gethostname()}.',
                f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
            sys.exit() # super important to do this because else the flagging file is removed and the entire fail safe doesnt work
        _delete_flagfile(args.isolatename, config_data)
    except Exception as exceptionmessage:
        _send_email(
            f'Error inserting isolate of {args.species} pipeline to bigsdb for sample {args.isolatename} on host {socket.gethostname()}.',
            f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        sys.exit()

        #todo find out if connections need to be closed
