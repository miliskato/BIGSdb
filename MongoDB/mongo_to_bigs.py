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

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.util.mongo_initialisation import MongoInitialisation
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.config import MONGO_CONFIG
from MongoDB.new_alleles_profile_clustering_from_mongo_to_bigs import \
    run_upload_new_alleles_profiles_clustering_from_mongo_to_bigs
from MongoDB.bad_samples_to_validation_bigs import bad_samples_to_validation_bigs
from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from bioit_custom_scripts.config import BIGSDB_CONFIG
from bioit_custom_scripts.main_results_inserter import main_results_inserter
from bioit_custom_scripts.insert_assembly import insert_assembly


def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=specieslist)
    argument_parser.add_argument('--single_sample', type=str, help=argparse.SUPPRESS)
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

def _return_datetimeobj_from_DMYhms(datetimestring: str) -> object:
    """
    return datetime object from Bert's custom datetime notation in Camel
    :param datetimestring: datetime sting in '%d/%m/%Y - %X' format
    :return: datetime.datetime object
    """
    return datetime.datetime.strptime(datetimestring, '%d/%m/%Y - %X').date()


def _return_datetimestr_from_YMD_to_DMYhms(datetimestring: str) -> str:
    """
    Revert SQL or other YMD to Bert's custom datetime notation in Camel
    :param datetimestring: datetime string in '%Y-%m-%d'
    :return: str
    """
    return datetime.datetime.strptime(datetimestring, '%Y-%m-%d').strftime('%d/%m/%Y - %X')


def mongo_to_bigs(species: str, single_sample: str = None) -> None:
    """
    Main function
    See argparse function for variables and their requiredness
    :param species:
    :param single_sample:
    :return:
    """
    # Parse Mongo config, second time because first time needed for argparse, and this time needed if function called from outside
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse Bigsdb config
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config = yaml.safe_load(handle)

    try:

        # Open collections
        mongoinit = MongoInitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections(
            config_data, species)

        # Connect to db and create cursor
        con_isolates, cur_isolates, con_seqdef, cur_seqdef = DatabaseConnection().connect_to_dbs_and_create_cursors(species)

        # call the function to insert new alleles and profiles
        run_upload_new_alleles_profiles_clustering_from_mongo_to_bigs(species)

        # send bad samples from the badqc_isolates collection to BIGSdb
        bad_samples_to_validation_bigs(species)

        if single_sample:
            query_single = isolates_collection.find_one({'_id': single_sample})
            if query_single is not None:
                listofdocuments = [query_single]
            else:
                _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                            f"Can not find document with _id '{single_sample}' in isolates",
                            bigsdb_config['mail'])
                raise Exception(
                    f"{os.path.basename(__file__)} fail on host {socket.gethostname()}: Can not find document with _id '{single_sample}' in isolates")

        else:
            listofdocuments = list(isolates_collection.find())

        for document in listofdocuments:
            cur_isolates.execute(f"SELECT COUNT(*) FROM isolates WHERE isolate='{document['results']['isolates_id']}'")
            sample_presence = cur_isolates.fetchall()
            if sample_presence[0][0] == 0:
                results_type = "new_isolate"
            elif sample_presence[0][0] == 1 and os.path.isfile(Path(bigsdb_config['failsafe']['flag_dir']) / '.'.join(
                    [document['results']['isolates_id'], bigsdb_config['failsafe']['flag_append']])):
                # isolate into bigsdb was started but failed during insertion.
                # if argument "new_isolate" is passed to main_results_inserter and it finds the flag, it will remove the isolate and the flag, and then recreate the flag and start insertion again.
                results_type = "new_isolate"
            else:
                results_type = "reanalysis"
                cur_isolates.execute(
                    f"SELECT latest_analysis_date FROM isolates WHERE isolate='{document['results']['isolates_id']}' ORDER BY id DESC")
                latest_analysis_date_bigs = cur_isolates.fetchall()[0][0]  # this appearently is a datetime object
                cur_isolates.execute(f"SELECT value FROM eav_text_hidden WHERE field='mongo_results_version' and isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{document['results']['isolates_id']}')")
                # as of 2022/12/22 mongo_results_version in bigs is changed version
                mongo_results_changed_version_bigs_query = cur_isolates.fetchall()
                if mongo_results_changed_version_bigs_query == []:
                    # Accounting for old samples that didnt have a version yet
                    mongo_results_changed_version_bigs = 1
                else:
                    mongo_results_changed_version_bigs = int(mongo_results_changed_version_bigs_query[0][0])
                if _return_datetimeobj_from_DMYhms(document['results']['analysis_date']) > latest_analysis_date_bigs:
                    new_results = document['results']
                    if new_results['changed_version'] == int(mongo_results_changed_version_bigs):
                        # results are same so do nothing
                        logging.info(
                            f"results_version might be different, but changed_version same in mongodb and bigsdb for {document['results']['isolates_id']}")
                        continue
                    else:
                        old_results_withpointers = old_isolateresults_collection.with_options(
                            read_concern=ReadConcern(level="majority")).find_one(
                            {'isolates_id': new_results['isolates_id'],
                             'changed_version': mongo_results_changed_version_bigs})
                        if old_results_withpointers is None:
                            # what if bigs has version 1, but mongo has version 3, but version 3 is no different from 1 and 2?
                            # Currently new versions are only created if there were changes so in case more than 2 versions different and missing then should send error.
                            _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                                        f"Can not find document in old isolate results collection for isolate {new_results['isolates_id']} and results version {mongo_results_changed_version_bigs}",
                                        bigsdb_config['mail'])
                            raise Exception(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}: Can not find document in old isolate results collection for isolate {new_results['isolates_id']} and results version {mongo_results_changed_version_bigs}")
                        else:
                            # replace the pointers in the old results by their actual contents
                            mongoquerying = Mongoquerying()
                            old_results = mongoquerying.query_old_results_and_replace_pointers(
                                old_isolateresults_collection, old_results_withpointers)
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
                            logging.info(
                                f"different version (more than 1 diff) but results same in mongodb and bigsdb {document['results']['isolates_id']}")
                            continue
                        # else if results changed, the for loop is continued and results are inserted into bigsdb as reanalysis
                else:
                    logging.info(
                        f"results version same in mongodb and bigsdb for sample {document['results']['isolates_id']}")
                    continue

            # continuation of for loop:
            # extract json file to be given to bigs
            jsonfile = f"{config_data.get('temp_dir')}/{document['results']['isolates_id']}_temp.json"
            with open(jsonfile, 'w') as handle:
                handle.write(json.dumps(document['results']))
            # todo modify mailadress
            main_results_inserter(document['results']['isolates_id'], 'bioit@sciensano.be', species, results_type, jsonfilepath=Path(jsonfile))
            os.remove(jsonfile)
            if results_type == 'new_isolate':
                insert_assembly(document['results']['isolates_id'], species, document['fasta_path'])
            logging.info(f"wrote new results version for {document['results']['isolates_id']} to bigsdb")

        DatabaseConnection().close_connections(con_isolates, con_seqdef)
    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config['mail'])
        raise Exception(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}")

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse Mongo config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(config_data['species'])

    # run main
    mongo_to_bigs(args.species,
                  single_sample=(args.single_sample if args.single_sample else None))
