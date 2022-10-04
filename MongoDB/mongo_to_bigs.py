# Hybrid between Bigs components and Mongodb components
# to be executed on bigs host of choice
# /home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_new/MongoDB/mongo_to_bigs.py --species listeria --pyvenvpythonpath /home/BIGSdb/3.9PythonVenv/bin/python3.9

import subprocess
import argparse
import logging
import sys
import os
import yaml
import json
from pathlib import Path
import datetime
from pymongo.read_concern import ReadConcern
import smtplib
from email.message import EmailMessage
import socket
import traceback

from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG
from bioit_custom_scripts.components.databaseconnection import Database_connection
from bioit_custom_scripts.config import BIGSDB_CONFIG

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    argument_parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='/home/BIGSdb/3.9PythonVenv/bin/python3.9')
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

def _return_datetimeobj_from_YMDhms(datetimestring: str):
    return datetime.datetime.strptime(datetimestring, '%d/%m/%Y - %X').date()

def _return_datetimestr_from_YMD_to_YMDhms(datetimestring: str):
    datetime.datetime.strptime(datetimestring, '%Y-%m-%d').strftime('%d/%m/%Y - %X')

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config = yaml.safe_load(handle)
    try:

        # Open collections
        mongoinit = Mongoinitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(config_data, args.species)

        # gather script path because not in same parent directory
        source = os.path.dirname(__file__)
        parent = os.path.join(source, '../')

        # Connect to db and create cursor
        cur_isolates, cur_seqdef = Database_connection().open_database_connections(args.species)

        for document in isolates_collection.find():
            cur_isolates.execute(f"SELECT COUNT(*) FROM isolates WHERE isolate='{document['results']['isolates_id']}'")
            sample_presence = cur_isolates.fetchall()
            if sample_presence[0][0] == 0:
                results_type = "new_isolate"
            elif sample_presence[0][0] == 1 and os.path.isfile(Path(bigsdb_config['failsafe']['flag_dir']) / '.'.join([document['results']['isolates_id'], bigsdb_config['failsafe']['flag_append']])):
                results_type = "new_isolate"
            else:
                results_type = "reanalysis"
                cur_isolates.execute(f"SELECT latest_analysis_date FROM isolates WHERE isolate='{document['results']['isolates_id']}'")
                latest_analysis_date_bigs = cur_isolates.fetchall()[0][0] # this appearently is a datetime object
                cur_isolates.execute(f"SELECT value FROM eav_text_hidden WHERE field='mongo_results_version'")
                mongo_results_version_bigs_query = cur_isolates.fetchall()
                print(mongo_results_version_bigs_query)
                if mongo_results_version_bigs_query == []:
                    mongo_results_version_bigs = 1
                else:
                    mongo_results_version_bigs = mongo_results_version_bigs_query[0][0]
                if _return_datetimeobj_from_YMDhms(document['results']['analysis_date']) > latest_analysis_date_bigs:
                    new_results = document['results']
                    print(new_results['results_version'], mongo_results_version_bigs + 1)
                    print(new_results["results_changed_since_last_version"])
                    if new_results['results_version'] == mongo_results_version_bigs + 1 and new_results["results_changed_since_last_version"] is False:

                        # results are same so do nothing
                        logging.info(f"different version (1 diff) but results same in mongodb and bigsdb for {document['results']['isolates_id']}")
                        continue
                    else:
                        old_results = old_isolateresults_collection.with_options(read_concern=ReadConcern(level="majority")).find_one({'isolates_id': new_results['isolates_id'], 'results_version': mongo_results_version_bigs})
                        if old_results is None:
                            # what if bigs has version 1, but mongo has version 3, but version 3 is no different from 1 and 2?
                            # Then need to look at the first at the first version higher, if None then this means that there were no changes
                            _send_email(f"{os.path.basename(__file__)}: Can not find document in old isolate results collection for isolate {new_results['isolates_id']} and results version {mongo_results_version_bigs}", "", bigsdb_config['mail'])
                            continue
                        some_result_changed = False
                        for mainkey in new_results.keys():
                            if isinstance(new_results[mainkey], dict):
                                for subkey in new_results[mainkey].keys():
                                    if mainkey not in old_results.keys():
                                        logging.info(f"{mainkey} not in old results")
                                        some_result_changed = True
                                    elif subkey == 'loci' or subkey == 'results' or subkey.startswith('hits'):
                                        if subkey not in old_results[mainkey].keys() or new_results[mainkey][subkey] != \
                                                old_results[mainkey][subkey]:
                                            # keep in mind that loci is a list: it seems as if loci are always outputted in the same order though so that is allright
                                            logging.info(f"{mainkey}{subkey} different or not in old")
                                            some_result_changed = True
                        if some_result_changed is False:
                            # results didnt change
                            logging.info(f"different version (more than 1 diff) but results same in mongodb and bigsdb {document['results']['isolates_id']}")
                            continue
                else:
                    logging.info(f"results version same in mongodb and bigsdb")
                    continue

            jsonfile = f"{document['results']['isolates_id']}_temp.json"
            with open(f"{document['results']['isolates_id']}_temp.json", 'w') as handle:
                handle.write(json.dumps(document['results']))
            def run_subprocess(custom_command):
                result = subprocess.run(
                    custom_command,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    shell=True,
                    executable='/bin/bash')
                if result.returncode != 0:
                    _send_email(
                        f"{os.path.basename(__file__)}: Error inserting {document['results']['isolates_id']} into bigsdb",
                        "",
                        bigsdb_config['mail'])
            run_subprocess(f"{args.pyvenvpythonpath} {os.path.join(parent, 'bioit_custom_scripts/main_results_inserter.py')} --jsonfilepath {jsonfile} --species {args.species} --isolatename {document['results']['isolates_id']} --uploadermailadress michael --results_type {results_type}")
            handle.close()
            os.remove(jsonfile)
            logging.info(f"wrote new results version for {document['results']['isolates_id']} to bigsdb")

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)}: mongo to bigs fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config['mail'])