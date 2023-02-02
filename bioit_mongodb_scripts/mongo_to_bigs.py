# Hybrid between Bigs components and Mongodb components
# to be executed on bigs host of choice
# /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_new/bioit_mongodb_scripts/mongo_to_bigs.py --species listeria --pyvenvpythonpath /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9

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
from pymongo.read_concern import ReadConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql_tables_queries import TblIsolates, TblEavTextHidden, TblSequenceBin, TblSeqBinStats
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data
from bioit_bigsdb_scripts.insert_assembly import insert_assembly
from bioit_bigsdb_scripts.main_results_inserter import main_results_inserter
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.config import MONGO_CONFIG
from bioit_mongodb_scripts.new_alleles_profile_clustering_from_mongo_to_bigs import \
    run_upload_new_alleles_profiles_clustering_from_mongo_to_bigs
from bioit_mongodb_scripts.samples_to_validation_bigs import samples_to_validation_bigs


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
        mongo_config_data = yaml.safe_load(handle)

    # Parse Bigsdb config
    bigsdb_config_data = get_bigsdb_config_data()

    try:

        # Open collections
        mongoinit = MongoInitialisation(species)
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()

        # call the function to insert new alleles and profiles
        run_upload_new_alleles_profiles_clustering_from_mongo_to_bigs(species)

        # send bad samples from the badqc_isolates collection to BIGSdb
        samples_to_validation_bigs(species)

        if single_sample:
            query_single = isolates_collection.find_one({'_id': single_sample})
            if query_single is not None:
                listofdocuments = [query_single]
            else:
                _send_email(f"{Path(__file__).name} fail on host {socket.gethostname()}",
                            f"Can not find document with _id '{single_sample}' in isolates",
                            bigsdb_config_data['mail'])
                raise Exception(
                    f"{Path(__file__).name} fail on host {socket.gethostname()}: Can not find document with _id '{single_sample}' in isolates")

        else:
            listofdocuments = list(isolates_collection.find())

        with TblIsolates(species) as isolates_psql_tbl:
            for document in listofdocuments:
                document_id = document['results']['isolates_id']
                sample_presence = isolates_psql_tbl.count_isolate((document_id,))
                if sample_presence[0][0] == 0:
                    results_type = "new_isolate"
                elif sample_presence[0][0] == 1 and os.path.isfile(Path(bigsdb_config_data['failsafe']['flag_dir']) / '.'.join(
                        [document_id, bigsdb_config_data['failsafe']['flag_append']])):
                    # isolate into bigsdb was started but failed during insertion.
                    # if argument "new_isolate" is passed to main_results_inserter and it finds the flag, it will remove the isolate and the flag, and then recreate the flag and start insertion again.
                    results_type = "new_isolate"
                else:
                    results_type = "reanalysis"
                    latest_analysis_date_bigs = (isolates_psql_tbl.select_latestanalysisdate_for_isolate((document_id)))[0][0]  # this appearently is a datetime object
                    with TblEavTextHidden(species) as isolates_eavth_psql_tbl:
                        mongo_results_changed_version_bigs_query = isolates_eavth_psql_tbl.select_mongo_resultsversion((document_id,))
                    # as of 2022/12/22 mongo_results_version in bigs is changed version
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
                                f"results_version might be different, but changed_version same in mongodb and bigsdb for {document_id}")
                            continue
                        else:
                            old_results_withpointers = old_isolateresults_collection.with_options(
                                read_concern=ReadConcern(level="majority")).find_one(
                                {'isolates_id': new_results['isolates_id'],
                                 'changed_version': mongo_results_changed_version_bigs})
                            if old_results_withpointers is None:
                                # what if bigs has version 1, but mongo has version 3, but version 3 is no different from 1 and 2?
                                # Currently new versions are only created if there were changes so in case more than 2 versions different and missing then should send error.
                                _send_email(f"{Path(__file__).name} fail on host {socket.gethostname()}",
                                            f"Can not find document in old isolate results collection for isolate {new_results['isolates_id']} and results version {mongo_results_changed_version_bigs}",
                                            bigsdb_config_data['mail'])
                                raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: Can not find document in old isolate results collection for isolate {new_results['isolates_id']} and results version {mongo_results_changed_version_bigs}")
                            else:
                                # replace the pointers in the old results by their actual contents
                                mongoquerying = Mongoquerying()
                                old_results = mongoquerying.query_old_results_and_replace_pointers(
                                    old_isolateresults_collection, old_results_withpointers)
                            some_result_changed = False
                            for mainkey in new_results:
                                if isinstance(new_results[mainkey], dict):
                                    for subkey in new_results[mainkey]:
                                        if mainkey not in old_results:
                                            logging.info(f"{mainkey} not in old results")
                                            some_result_changed = True
                                        elif subkey == 'loci' or subkey == 'results' or subkey.startswith('hits'):
                                            if subkey not in old_results[mainkey] or new_results[mainkey][subkey] != \
                                                    old_results[mainkey][subkey]:
                                                # keep in mind that loci is a list: it seems as if loci are always outputted in the same order though so that is allright
                                                logging.info(f"{mainkey}{subkey} different or not in old")
                                                some_result_changed = True
                            if some_result_changed is False:
                                # results didnt change
                                logging.info(
                                    f"different version (more than 1 diff) but results same in mongodb and bigsdb {document_id}")
                                continue
                            # else if results changed, the for loop is continued and results are inserted into bigsdb as reanalysis
                    else:
                        logging.info(
                            f"results version same in mongodb and bigsdb for sample {document_id}")
                        continue
    
                # continuation of for loop:
                # extract json file to be given to bigs
                jsonfile = f"{mongo_config_data.get('temp_dir')}/{document_id}_temp.json"
                if document.get('validation'):
                    # add validation metadata to results in order to be able to insert them into BIGSdb
                    document['results']['validation'] = document['validation']
                with open(jsonfile, 'w') as handle:
                    handle.write(json.dumps(document['results']))
                # todo modify mailadress
                main_results_inserter(document_id, 'bioit@sciensano.be', species, results_type, jsonfilepath=Path(jsonfile))
                os.remove(jsonfile)
                if results_type == 'new_isolate':
                    insert_assembly(document_id, species, document['fasta_path'])
                elif results_type == 'reanalysis' and document['validation']['type'] == 'resequencing':
                    last_two_validation_dates = isolates_psql_tbl.select_validationdate_for_isolate((document_id,))
                    # select to check that the previous versions validation date is different than the current
                    if last_two_validation_dates[0][0] != last_two_validation_dates[1][0]:
                        # revert the changes done in maininserter that move the assembly to the newest version
                        with TblSequenceBin(species) as isolates_seqbin_psql_tbl:
                            isolates_seqbin_psql_tbl.update_sequencebin_newversion(
                                (document_id, document_id))
                        with TblSeqBinStats(species) as isolates_seqbinstats_psql_tbl:
                            isolates_seqbinstats_psql_tbl.update_seqbinstats_newversion(
                                (document_id, document_id))
                        insert_assembly(document_id, species, document['fasta_path'])
    
                logging.info(f"wrote new results version for {document_id} to bigsdb")

    except Exception as exceptionmessage:
        _send_email(f"{Path(__file__).name} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", bigsdb_config_data['mail'])
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse Mongo config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        mongo_config_data = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(mongo_config_data['species'])

    # run main
    mongo_to_bigs(args.species,
                  single_sample=(args.single_sample if args.single_sample else None))
