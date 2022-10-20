from pymongo import MongoClient
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
# import dnspython # somehow this package is a requirement without actually needing to be imported, probably imported in pymongo
import yaml
import argparse
from pathlib import Path
import logging
import datetime
import sys
import re
import json
import smtplib
from email.message import EmailMessage
import socket
import traceback
import os
from util.mongo_results import Mongoresults
from util.mongo_querying import Mongoquerying
from util.mongo_initialisation import Mongoinitialisation
from util.mongo_custom_clustering import MongoCustomClustering
from config import MONGO_CONFIG
from MongoDB.config import HIERCC_CONFIG

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

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--jsonfilepath", required=True, type=Path)
    parser.add_argument("--species", required=True, type=str,
                        choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella','listeria_test'])
    parser.add_argument("--results_type", required=True, type=str, choices=['new_isolate', 'reanalysis'])
    parser.add_argument("--fastafilepath", required=False, type=str)
    parser.add_argument("--vcffilepath", required=False, type=str)
    parser.add_argument("--technical_id", required=True, type=str)
    return parser.parse_args()


def _write_document(opened_collection, json_input: dict):
    collection_write = opened_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(json_input)
    logging.debug(f"Writing {collection_write.inserted_id} in collection {opened_collection}")
    return collection_write.inserted_id


def _new_isolate(technical_id: str, vcffilepath: str, fastafilepath: str,
                 results: dict) -> dict:
    """
    Initialises new isolate dictionary including its results
    :param technical_id:
    :param vcffilepath:
    :param fastafilepath:
    :param results:
    :return:
    """
    results["results_version"] = 1
    new_isolate_dict = {"_id": technical_id,
                        "vcf_path": vcffilepath,
                        "fasta_path": fastafilepath,
                        "previous_latest_results_version": "", #_write_document(isolateresults_collection, results)
                        "creation_date": datetime.datetime.utcnow(),
                        "latest_analysis_date": _return_YMD_from_YMDhms(results["analysis_date"]),
                        "results": results}
    return new_isolate_dict

def prepend_string_dot_to_dict_keys(input_dictionary, prepending: str = 'results'):
    """
    This function is designed to update only results that have been reanalyzed; by using dot notation in the dicts only the relevant assays/metadata are updated upon reanalysis.
    The function can of course serve other purposes
    :param input_dictionary:
    :param prepending: string to prepend to dictionary keys separated by dot
    :return: dict with prepended string joined with dot
    """
    keydict = {}
    import copy
    input_dictionary_copy = copy.deepcopy(input_dictionary)
    for key in input_dictionary.keys():
        if key == 'qc':
            for subkey in input_dictionary[key]:
                input_dictionary_copy['.'.join([key, subkey])] = input_dictionary_copy[key][subkey]
            input_dictionary_copy.pop('qc')
    for key in input_dictionary_copy.keys():
            keydict[key] = '.'.join([prepending, key])
    return dict((keydict[key], value) for (key, value) in input_dictionary_copy.items())

def find_allele_number_new_entry(hashed_AD_collection):
    query_hash_db_size = hashed_AD_collection.count_documents({"scheme": 'cgmlst'})
    if query_hash_db_size == 0:
        return 'Temp_1'
    else:
        return f'Temp_{query_hash_db_size + 1}'


def find_hashes_in_results_and_add_to_collection(results: dict, mongoinit: object, config_data: dict, species: str):
    hashed_AD_collection = mongoinit.initialise_hashing_collection(config_data, species)
    for typing_scheme in ['mlst', 'cgmlst', 'mlst_warwick', 'mlst_pasteur']:
        if typing_scheme in results.keys():
            for locus_index, allele_info in enumerate(results[typing_scheme]['loci']):
                # check if allele designation is md5 hash (32 char combination of letters andor numbers)
                if re.findall(r'(?i)(?<![a-z0-9])[a-f0-9]{32}(?![a-z0-9])', allele_info['Allele']):
                    existing_document = hashed_AD_collection.with_options(read_concern=ReadConcern(level="majority")).find_one({"scheme": typing_scheme, "locus": allele_info['Locus'], "hashed_allele": allele_info['Allele']})
                    if existing_document is None:
                        temp_allele = find_allele_number_new_entry(hashed_AD_collection)
                        _write_document(hashed_AD_collection, {"scheme": typing_scheme,
                                                               "locus": allele_info['Locus'],
                                                               "hashed_allele": allele_info['Allele'],
                                                               "allele_sequence" : allele_info['Allele_sequence'],
                                                               "encountered_count": 1,
                                                               "resolved_AD": 0,
                                                               "allele_number": temp_allele,
                                                               "insertion_date": datetime.datetime.utcnow()
                                                               })
                    else:
                        temp_allele = existing_document["allele_number"]
                        hashed_AD_collection.with_options(write_concern=WriteConcern(w="majority")).update_one({"_id": existing_document['_id']},
                                                                                                               {"$inc": {"encountered_count": 1}})
                        logging.info(f"hashed allele '{allele_info['Allele']}' encounter incremented by one")
                    results[typing_scheme]['loci'][locus_index].pop('Allele_sequence')
                    results[typing_scheme]['loci'][locus_index]['Allele'] = temp_allele #replace in the results the name of the allele (no hash anymore)
                    return results

def _return_YMD_from_YMDhms(datetimestring: str):
    return datetime.datetime.strptime(datetimestring, '%d/%m/%Y - %X').strftime('%Y-%m-%d')

if __name__ == '__main__':
    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    try:
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Open collections
        mongoinit = Mongoinitialisation()
        isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(config_data, args.species)
        st_collection, cluster_membership_collection = \
            mongoinit.initialise_clustering_collections(config_data, args.species)
        mongoquerying = Mongoquerying()

        # If statement for reanalysis or new
        if args.results_type == "new_isolate":
            if args.technical_id in mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id") or args.technical_id in mongoquerying._query_list_of_all_distinct_values(isolates_badqc_collection, "_id"):
                raise RuntimeError('This technical id is already present in the isolates collection')
            else:
                # todo check if fasta path and vcf path are real?
                mongoresults = Mongoresults()
                records = json.load(open(args.jsonfilepath, 'r'))
                records["isolates_id"] = args.technical_id
                # Change date format
                ## to do in queries themselves because else error: TypeError: 'datetime.datetime' object is not iterable
                # QC check for failed qc to not be integrated in main db
                sample_quality = 'good'
                try:
                    for qc_type in records['qc']:
                        for key in records['qc'][qc_type]:
                            if key.endswith('status') and records['qc'][qc_type][key] == 'Failed' and not key == 'analysis_date': # and not (records['qc'][qc_type][key] == 'OK' or records['qc'][qc_type][key] == 'Warning'): # todo check logic
                                sample_quality = 'bad'
                except:
                    raise RuntimeError('No qc values found in the given results')

            if sample_quality == 'good':
                records = find_hashes_in_results_and_add_to_collection(records, mongoinit, config_data, args.species)
                _write_document(isolates_collection, _new_isolate(args.technical_id, args.vcffilepath, args.fastafilepath,
                                                                  records))
                logging.info(f"Wrote new isolate {args.technical_id} and its result to {args.species} database")
                hashed_AD_collection = mongoinit.initialise_hashing_collection(config_data, args.species)
                clustering_input = mongoquerying._query_typing_results_by_technicalids_and_scheme(isolates_collection,
                                                                                                  hashed_AD_collection,
                                                                                                  scheme="cgmlst",
                                                                                                  technicalids=
                                                                                              [args.technical_id])
                custom_clustering = MongoCustomClustering(clustering_input[0], clustering_input[1], args.species)
                logging.info(f"Running the clustering for the isolate {args.technical_id}")
                sequence_type = custom_clustering.run_custom_clustering(st_collection,
                                                                        cluster_membership_collection, HIERCC_CONFIG["clustering_thresholds"])
                isolates_collection.find_one_and_update({"_id": records["isolates_id"]},
                                                        {"$set": {"ST": sequence_type}})
            else:
                _write_document(isolates_badqc_collection, _new_isolate(args.technical_id, args.vcffilepath, args.fastafilepath,
                                                                  records))
                logging.warning(f"New isolate {args.technical_id} failed quality control for one or more checks. It's results were written to the 'isolates_badqc' collection in the {args.species} database")
                if sample_quality == 'good':
                    records = find_hashes_in_results_and_add_to_collection(records, mongoinit, config_data, args.species)
                    _write_document(isolates_collection, _new_isolate(args.technical_id, args.vcffilepath, args.fastafilepath,
                                                                      records))
                    logging.info(f"Wrote new isolate {args.technical_id} and its result to {args.species} database")
                else:
                    _write_document(isolates_badqc_collection, _new_isolate(args.technical_id, args.vcffilepath, args.fastafilepath,
                                                                      records))
                    logging.warning(f"New isolate {args.technical_id} failed quality control for one or more checks. It's results were written to the 'isolates_badqc' collection in the {args.species} database")


        elif args.results_type == "reanalysis":
            # todo the current implementation moves the old results to the archive BUT seeing as results are possibly fractional
            #  from different reanalysis steps it is never sure when which results were updated.
            #  Maybe the newest results should also be written to a separate collection in order to easily know what actually changed?
            #  Current dot notation only covers the assay headers, so within assays everything is overwritten, no matter if the number of fields differs.
            mongoresults = Mongoresults()
            new_results_handle = json.load(open(args.jsonfilepath, 'r'))
            new_results = prepend_string_dot_to_dict_keys(new_results_handle)
            new_results["results.isolates_id"] = args.technical_id
            old_results = mongoquerying._query_docs_by_ids(isolates_collection, [args.technical_id])[0]['results']
            some_result_changed = False
            for mainkey in new_results_handle.keys():
                if isinstance(new_results_handle[mainkey], dict):
                    for subkey in new_results_handle[mainkey].keys():
                        if mainkey not in old_results.keys():
                            logging.info(f"{mainkey} not in old results")
                            some_result_changed = True
                        elif subkey == 'loci' or subkey == 'results' or subkey.startswith('hits'):
                            if subkey not in old_results[mainkey].keys() or new_results_handle[mainkey][subkey] != old_results[mainkey][subkey]:
                                # keep in mind that loci is a list: it seems as if loci are always outputted in the same order though so that is allright
                                logging.info(f"{mainkey}{subkey} different or not in old")
                                some_result_changed = True
            if some_result_changed is True:
                new_results["results.results_version"] = old_results["results_version"] + 1
                isolates_collection.with_options(write_concern=WriteConcern(w="majority")).update_one({"_id": args.technical_id}, {
                    "$set": {**new_results,
                             "results.results_changed_since_last_version": True,
                             "latest_analysis_date": _return_YMD_from_YMDhms(new_results["results.analysis_date"]),
                             "previous_latest_results_version": _write_document(isolateresults_collection, old_results)}})
                logging.info(f"Wrote new results and linked to isolate {args.technical_id} in {args.species}")
            else:
                # results version is not changed, it does not really matter how many analyses have already been performed with the same result
                # new results still needs to be added because it modifies the analysis dates, db dates and also tool versions if these changed
                isolates_collection.with_options(write_concern=WriteConcern(w="majority")).update_one({"_id": args.technical_id}, {
                    "$set": {**new_results,
                             "results.results_changed_since_last_version": False,
                             "latest_analysis_date": _return_YMD_from_YMDhms(new_results["results.analysis_date"])}})
                logging.info(f"New results were not different from old results for {args.technical_id} in {args.species}, updated analysis dates and db versions.")

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)}: mongo upload fail on host {socket.gethostname()}",
                f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
