import argparse
import datetime
import json
import logging
import os
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
from bioit_custom_scripts.components.maininserter import MainInserter
from bioit_custom_scripts.components.tsv_typingresultsinserter import TsvTypingResultsInserter
from bioit_custom_scripts.components.tsv_genedetectionresultsinserter import TsvGeneDetectionResultsInserter
from bioit_custom_scripts.components.json_typingresultsinserter import JsonTypingResultsInserter
from bioit_custom_scripts.components.json_genedetectionresultsinserter import JsonGeneDetectionResultsInserter


def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    mutually_exclusive_group = argument_parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--tsvfilepath', type=Path)
    mutually_exclusive_group.add_argument('--jsonfilepath', type=Path)
    argument_parser.add_argument('--isolatename', required=True, type=str)
    argument_parser.add_argument('--uploadermailadress', required=True, type=str)
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=specieslist)
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


def __make_flagfilepath(isolatename: str, config: dict) -> Path:
    """
    Returns the flag file path
    :param isolatename: part of flagname
    :param config: config containing the failsafe settings
    :return: flag file path
    """
    return Path(config['failsafe']['flag_dir']) / '.'.join([isolatename, config['failsafe']['flag_append']])


def _fail_safe_mechanism(isolatename: str, config: dict, analysis_date: str, cur_isolates: object) -> None:
    """
    Creates a flagfile if insertion is started and no flagfile is present.
    else insertion is started and flag file is present: remove highest version of sample and
     reinsert if multiple versions, if only one version, sample is reinserted in the main workflow below
    :param isolatename:
    :param config: config containing the failsafe settings
    :param analysis_date: analysis date needed to insert new isolate version
    :param cur_isolates: isolate database connection object
    :return: flag file present
    """
    try:
        if not os.path.isdir(Path(config['failsafe']['flag_dir'])):
            os.makedirs(Path(config['failsafe']['flag_dir']), exist_ok=True)
            os.chmod(Path(config['failsafe']['flag_dir']), 0o777)
        flagfilepath = __make_flagfilepath(isolatename, config)
        if os.path.isfile(flagfilepath):
            logging.warning(f"fail safe mechanism detects that the bigsdb insertion for sample {isolatename} was started but didnt finish. Removing {isolatename} from Bigsdb to be able to restart inserting.")
            sqlquery = """SELECT COUNT(*) FROM isolates WHERE isolate=%s;"""
            cur_isolates.execute(sqlquery, (isolatename,))
            nr_of_versions = cur_isolates.fetchall()[0][0]
            if nr_of_versions > 1:
                sqlquery = """UPDATE isolates SET new_version=NULL WHERE id=(SELECT MIN(id) FROM isolates WHERE id in (SELECT id FROM isolates WHERE isolate=%s ORDER BY id DESC LIMIT 2));"""
                cur_isolates.execute(sqlquery, (isolatename,))
                sqlquery = """DELETE FROM isolates WHERE isolate='{isolatename}' AND id=(SELECT MAX(id) FROM isolates WHERE isolate=%s);"""
                cur_isolates.execute(sqlquery, (isolatename,))
                sqlquery = """
                           INSERT INTO isolates(id, isolate, sender, curator, date_entered, datestamp, uploader, latest_analyis_date) 
                           VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM isolates) IS NULL THEN 1 
                           ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), %s, 1, 1, 
                           (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), 
                           (SELECT uploader FROM isolates WHERE isolate=%s AND id=(SELECT MAX(id) FROM isolates WHERE isolate=%s)), %s);"""
                cur_isolates.execute(sqlquery, (isolatename, isolatename, isolatename, datetime.datetime.strptime(analysis_date, '%d/%m/%Y - %X').strftime('%Y-%m-%d')))
                sqlquery = """
                           UPDATE isolates SET new_version=(SELECT MAX(id) FROM isolates WHERE isolate=%s) 
                           WHERE isolate=%s AND new_version IS NULL AND id!=(SELECT MAX(id) 
                           FROM isolates WHERE isolate=%s);"""
                cur_isolates.execute(sqlquery, (isolatename, isolatename, isolatename))
            else:
                sqlquery = """DELETE FROM isolates WHERE isolate=%s AND id=(SELECT MAX(id) FROM isolates WHERE isolate=%s);"""
                cur_isolates.execute(sqlquery, (isolatename, isolatename))
        else:
            flagfilepath.touch()
            os.chmod(flagfilepath, 0o777)
            logging.info(f"flagfilepath {flagfilepath}")
    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}", f"{exceptionmessage}\n{traceback.format_exc()}", config['mail'])
        raise Exception(f"{os.path.basename(__file__)}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")


def _delete_flagfile(isolatename: str, config: dict) -> None:
    """
    :param isolatename:
    :param config: config containing the failsafe settings
    :return: Removes flagfile
    """
    flagfilepath = __make_flagfilepath(isolatename, config)
    try:
        os.remove(flagfilepath)
    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}", f"{exceptionmessage}\n{traceback.format_exc()}", config['mail'])
        raise Exception(f"{os.path.basename(__file__)}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")

def main_results_inserter(isolatename: str, uploadermailadress: str, species: str, results_type: str, jsonfilepath: Path = None, tsvfilepath: Path = None) -> None:
    """
    Main function
    See argparse function for variables and their requiredness
    :param isolatename:
    :param uploadermailadress:
    :param species:
    :param results_type:
    :param jsonfilepath:
    :param tsvfilepath:
    :return:
    """
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # parse output
    if tsvfilepath:
        sample_output_dict = {}
        handle = open(tsvfilepath, 'r').readlines()
        for line in handle:
            sample_output_dict[line.split('\t')[0]] = line.split('\t')[1].strip('\n')
    elif jsonfilepath:
        records = json.load(open(jsonfilepath, 'r'))
        if 'results' in records.keys():
            # records come from mongodb
            sample_output_dict = records['results']
        else:
            # records come from the pipeline directly
            sample_output_dict = records
    else:
        _send_email(
            f'{os.path.basename(__file__)}: Error inserting output of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}, need either jsonfilepath or tsvfilepath.',
            "", config_data['mail'])
        sys.exit()
    # Logic
    try:
        # Connect to db and create cursors
        (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        # fail safe mechanism is initated at the same time of the isolate insertion, but after connecting to the PSQL db's
        maininserter = MainInserter(isolatename, species, cur_isolates, cur_seqdef, sample_output_dict)
        _fail_safe_mechanism(isolatename, config_data, sample_output_dict['analysis_date'], cur_isolates)
        if results_type == 'new_isolate':
            maininserter.insert_new_isolate(uploadermailadress)
        elif results_type == 'reanalysis':
            maininserter.insert_new_isolate_version()
        try:
            maininserter.insert_main_metadata()
            if tsvfilepath:
                TsvTypingResultsInserter().insert_typing_results(isolatename, species, config_data['species'][species]['typing_schemes'], sample_output_dict, cur_isolates, cur_seqdef)
                TsvGeneDetectionResultsInserter().insert_genedetection_results(isolatename, species, config_data['species'][species]['genedetection_schemes'], sample_output_dict, cur_isolates, cur_seqdef)
            elif jsonfilepath:
                JsonTypingResultsInserter(isolatename, species, cur_isolates, cur_seqdef, sample_output_dict).insert_typing_results(config_data['species_json'][species]['typing_schemes'])
                JsonGeneDetectionResultsInserter(isolatename, species, cur_isolates, cur_seqdef, sample_output_dict).insert_genedetection_results(config_data['species_json'][species]['genedetection_schemes'])
            logging.info('Finished inserting results')
        except Exception as exceptionmessage:
            _send_email(
                f'{os.path.basename(__file__)}: Error inserting output of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.',
                f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
            raise Exception(f'{os.path.basename(__file__)}: Error inserting output of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            # super important to raise exception because else the flagging file is removed and the entire fail safe doesnt work
        _delete_flagfile(isolatename, config_data)
        DatabaseConnection().close_connections(con_isolates, con_seqdef)
    except Exception as exceptionmessage:
        _send_email(
            f'{os.path.basename(__file__)}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.',
            f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        raise Exception(f'{os.path.basename(__file__)}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Read the global config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(list(config_data['species'].keys()))

    # run main
    main_results_inserter(args.isolatename, args.uploadermailadress, args.species, args.results_type, jsonfilepath=(args.jsonfilepath if args.jsonfilepath else None), tsvfilepath=(args.tsvfilepath if args.tsvfilepath else None))
