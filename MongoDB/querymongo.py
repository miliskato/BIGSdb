import argparse
import yaml
import pprint
import pymongo
from util.mongo_querying import Mongoquerying
from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG
from util.mongo_hiercc_clustering import MongoHierCCClustering

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    return parser.parse_args()


if __name__ == '__main__':
    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(config_data, args.species)
    st_collection, hiercc_results_collection, distance_matrix_collection = \
        mongoinit.initialise_hiercc_collections(config_data, args.species)
    # isolates_collection.drop()
    # isolateresults_collection.drop()
    mongoquerying = Mongoquerying()

    mongoquerying.query_failed_causes(isolates_badqc_collection)

    # print([docs for docs in isolates_collection.find({'_id': 'S14BD00df001'})])
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
    #pprint.pprint(isolates_collection.find_one({'latest_analysis_date': {'$gte': start, '$lt': end}}))
    # headers = st_collection.find_one({'ID': 'headers'})['headers']
    # input_data = ['0'] * (len(headers)-1600)
    # input_data = input_data + (['1'] * 1600)
    # hcc = MongoHierCCClustering(headers, input_data,'listeria')
    # result = hcc.run_hiercc_clustering(st_collection, hiercc_results_collection)
    # print(result)
    # result = mongoquerying.find_isolates_cgmlst_distance("S14BD02863", 100, isolates_collection, distance_matrix_collection)
    # print(result)

