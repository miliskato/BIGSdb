import argparse
import yaml
import pprint
import pymongo
import logging
import sys
import os

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG

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
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(config_data['species'])

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit.initialise_collections(config_data, args.species)
    # isolates_collection.drop()
    # isolateresults_collection.drop()
    mongoquerying = Mongoquerying()

    # print(isolates_collection.find_one()['results'].keys())
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

    mongoquerying.query_what_changed_compared_to_previous('S14BD00001_R1_001', isolates_collection, isolateresults_collection)

    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, '_id'))
    # for result in mongoquerying._query_previous_latest_results_by_technicalids(isolates_collection, isolateresults_collection,
    #                                                            mongoquerying._query_list_of_all_distinct_values(
    #                                                                    isolates_collection, "_id")):
    #     if 'testiffail' in result.keys():
    #         print(result['isolates_id'], result['testiffail'])
    # print((mongoquerying._query_docs_by_ids(isolates_collection, ['technical_id_test_fqsdad']))[0].results)
    # print('test')
    # # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id"))
    # # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "isolate_results"))
    # # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "vcf_path"))
    # # print(_query_collection(isolates_collection))
    # print(mongoquerying._query_previous_latest_results_by_technicalids(isolates_collection, isolateresults_collection, ['technical_test_new', 'technical_id_test_165hhh']))
    # print(mongoquerying._query_previous_latest_results_by_technicalids(isolates_collection, isolateresults_collection, mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id")))

    # test = mongoquerying._query_typing_results_by_technicalids_and_scheme(isolates_collection,
    # isolateresults_collection, scheme="cgmlst", technicalids=["S14BD00001"])
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
