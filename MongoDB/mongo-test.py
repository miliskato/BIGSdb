from pymongo import MongoClient
#import dnspython
import yaml
import argparse
from pathlib import Path
import logging

from util.mongo_results import Mongoresults
from util.mongo_querying import Mongoquerying
from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--tsvfilepath", required=True, type=Path)
    parser.add_argument("--species", required=True, type=str, choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    parser.add_argument("--results_type", required=True, type=str, choices=['new_isolate', 'reanalysis'])
    parser.add_argument("--fastafilepath", required=False, type=str)
    parser.add_argument("--vcffilepath", required=False, type=str)
    parser.add_argument("--technical_id", required=True, type=str)
    return parser.parse_args()

def _write_document(opened_collection, json_input: dict):
    collection_write = opened_collection.insert_one(json_input)
    logging.debug(f"Writing {collection_write.inserted_id} in collection {opened_collection}")
    return collection_write.inserted_id

if __name__ == '__main__':

    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection = mongoinit._initialise_collections(config_data, args.species)
    mongoquerying = Mongoquerying()
    # _query_list_of_all_values(isolates_collection)
    # _query_list_of_all_values(species_database, "isolate_results")
    print(mongoquerying._query_list_of_all_values(isolates_collection, "vcf_path"))
    # print(_query_collection(isolates_collection))
    print(mongoquerying._query_results_by_technicalids(isolates_collection, isolateresults_collection, ['technical_test_new', 'technical_id_test_165hhh']))

    # If statement for reanalysis or new
    args.technical_id = "technical_test_dqqdsqs54"
    if args.results_type == "new_isolate":
        if args.technical_id in mongoquerying._query_list_of_all_values(isolates_collection, "_id"):
            raise RuntimeError('This technical id is already present in the isolates collection')
        else:
            mongoresults = Mongoresults()
            records = mongoresults.parse_output(args.species, args.tsvfilepath)
            records["isolates_id"] = args.technical_id
            _write_document(isolates_collection, {"_id": args.technical_id, "vcf_path": args.vcffilepath, "fasta_path": args.fastafilepath, "latest_results_version": _write_document(isolateresults_collection, records)})
    elif args.results_type == "reanalysis":
        mongoresults = Mongoresults()
        records = mongoresults.parse_output(args.species, args.tsvfilepath)
        records["isolates_id"] = args.technical_id
        isolates_collection.update_one({"_id": args.technical_id}, { "$set": {"latest_results_version": _write_document(isolateresults_collection, records)}})

