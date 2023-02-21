import argparse
import logging
import sys
from pathlib import Path

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data

def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    return parser.parse_args()


if __name__ == '__main__':
    """
    This script is a playground script, it allows to test anything concerning MongoDB easily
    """
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = _parse_arguments(list(mongo_config_data['species']))

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Open collections
    mongoinit = MongoInitialisation(args.species, alternate_connection_string=True)
    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
    headers_collection = mongoinit.initialise_headers_collection()
    # isolates_collection.drop()
    # old_isolateresults_collection.drop()
    mongoquerying = Mongoquerying()
    from pymongo.read_concern import ReadConcern
    #print(list(old_isolateresults_collection.with_options(read_concern=ReadConcern(level="majority")).\
    #            find({'isolates_id': 'test_mainmongo', 'analysis_date': {'$gte': '03/02/2023 - 00:00:00'}}, {'analysis_date':1}).sort('analysis_date', -1)))
    print(mongoquerying.get_any_results_version('test_mainmongo', 'analysis_date', '2024-01-01', isolates_collection, old_isolateresults_collection, headers_collection))
    # result_isolates = isolates_collection.find_one({'_id': '11-090'})
    # print(list(isolates_collection.find({'_id': 'test'})))
    # print(isolates_badqc_collection.find_one({'_id': '11-090'}, {'fasta_path':1}) if result_isolates is None else result_isolates)
    # print(result_isolates if result_isolates is not None else isolates_badqc_collection.find_one({'_id': '11-090'},  {'fasta_path':1}))
    # print(isolates_collection.find_one()['results'])
    # mongoquerying.query_failed_causes(isolates_badqc_collection)
    # list_of_lists = [docs['results']['species_confirmation']['loci'] for docs in isolates_collection.find()]
    # import itertools
    # list_all = list(itertools.chain.from_iterable(list_of_lists))
    # print([':'.join([locus['Locus'], locus['Allele']]) for locus in list_all])
    # for locus in list_all:
    #     import re
    #     if re.findall(r'(?i)(?<![a-z0-9])[a-f0-9]{32}(?![a-z0-9])', locus['Allele']):
    #         print(':'.join([locus['Locus'], locus['Allele']]))
    # print([docs for docs in isolates_collection.find({},{'_id': 1})])

    # mongoquerying.query_what_changed_compared_to_previous('S14BD00001_R1_001', isolates_collection, old_isolateresults_collection)

    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, '_id'))
    # for result in mongoquerying._query_previous_latest_results_by_technicalids(isolates_collection, old_isolateresults_collection,
    #                                                            mongoquerying._query_list_of_all_distinct_values(
    #                                                                    isolates_collection, "_id")):
    #     if 'testiffail' in result:
    #         print(result['isolates_id'], result['testiffail'])
    # print((mongoquerying._query_docs_by_ids(isolates_collection, ['technical_id_test_fqsdad']))[0].results)
    # print('test')
    # # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id"))
    # # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "isolate_results"))
    # # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "vcf_path"))
    # # print(_query_collection(isolates_collection))
    # print(mongoquerying._query_previous_latest_results_by_technicalids(isolates_collection, old_isolateresults_collection, ['technical_test_new', 'technical_id_test_165hhh']))
    # print(mongoquerying._query_previous_latest_results_by_technicalids(isolates_collection, old_isolateresults_collection, mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id")))

    # test = mongoquerying._query_typing_results_by_technicalids_and_scheme(isolates_collection,
    # old_isolateresults_collection, scheme="cgmlst", technicalids=["S14BD00001"])
    # print(test[1])
    # pprint.pprint(isolates_collection.distinct('latest_analysis_date'))
    # start = datetime(2022, 7, 13, 7, 56, 4)
    # end = datetime(2022, 10, 24, 7, 52, 4)
    # print(isolates_collection.find_one({'latest_analysis_date': {'$lt': end, '$gte': start}, 'porta': 'A0'}))
    # print(isolates_collection.find_one({'latest_analysis_date': {'$lt': end}}))
    # print(isolates_collection.find_one({'latest_analysis_date': {'$gte': start}}))
    # pprint.pprint(isolates_collection.find_one({'latest_analysis_date': {'$gte': start, '$lt': end}}))
    # headers = st_collection.find_one({'ID': 'headers'})['headers']
    # input_data = ['0'] * (len(headers)-1600)
    # input_data = input_data + (['1'] * 1600)
    # hcc = MongoHierCCClustering(headers, input_data,'listeria')
    # result = hcc.run_hiercc_clustering(st_collection, hiercc_results_collection)
    # print(result)
    # result = mongoquerying.find_isolates_cgmlst_distance("S14BD02863", 100, isolates_collection, distance_matrix_collection)
    # print(result)
