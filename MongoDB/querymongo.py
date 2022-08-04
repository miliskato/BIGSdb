import argparse
import yaml

from util.mongo_querying import Mongoquerying
from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG
from datetime import datetime

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str, choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    return parser.parse_args()

if __name__ == '__main__':
    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection = mongoinit._initialise_collections(config_data, args.species)
    # isolates_collection.drop()
    # isolateresults_collection.drop()
    mongoquerying = Mongoquerying()
    for result in mongoquerying._query_results_by_technicalids(isolates_collection, isolateresults_collection, mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id")):
        if 'testiffail' in result.keys():
            print(result['isolates_id'],result['testiffail'])
    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id"))
    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "isolate_results"))
    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "vcf_path"))
    # print(_query_collection(isolates_collection))
    # print(mongoquerying._query_results_by_technicalids(isolates_collection, isolateresults_collection, ['technical_test_new', 'technical_id_test_165hhh']))
    # print(mongoquerying._query_results_by_technicalids(isolates_collection, isolateresults_collection, mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id")))

    print(mongoquerying._query_typing_results_by_technicalids_and_scheme(isolates_collection, isolateresults_collection, scheme="cgmlst"))
