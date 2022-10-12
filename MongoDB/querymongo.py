import argparse
import yaml
import pprint
import pymongo
from util.mongo_querying import Mongoquerying
from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG
#from util.mongo_hiercc_clustering import MongoHierCCClustering
#from util.clustering_maker import ClusteringMaker
from MongoDB.util.distance_matrix_computer import DistanceMatrixComputer
from MongoDB.util.clustering_maker import ClusteringMaker
from MongoDB.util.alternative_clustering_maker import AlternativeClusteringMaker
from MongoDB.util.clustering_maker_custom import ClusteringMakerCustom
import logging
import sys

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

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(config_data, args.species)
    st_collection, hiercc_results_collection, cluster_membership_collection = \
        mongoinit.initialise_hiercc_collections(config_data, args.species)
    # isolates_collection.drop()
    # isolateresults_collection.drop()
    mongoquerying = Mongoquerying()
    # for result in mongoquerying._query_results_by_technicalids(isolates_collection, isolateresults_collection,

    #print(isolates_collection.find_one()['results'].keys())
    #mongoquerying.query_failed_causes(isolates_badqc_collection)
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
    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id"))
    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "isolate_results"))
    # print(mongoquerying._query_list_of_all_distinct_values(isolates_collection, "vcf_path"))
    # print(_query_collection(isolates_collection))
    # print(mongoquerying._query_results_by_technicalids(isolates_collection, isolateresults_collection, ['technical_test_new', 'technical_id_test_165hhh']))
    # print(mongoquerying._query_results_by_technicalids(isolates_collection, isolateresults_collection, mongoquerying._query_list_of_all_distinct_values(isolates_collection, "_id")))

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
    #result = mongoquerying.find_isolates_cgmlst_distance("S14BD02863", 100, isolates_collection, distance_matrix_collection)
    #print(result)

    # hc_number = mongoquerying.find_HC_numbers_for_isolate("S14BD02863", isolates_collection, hiercc_results_collection, 'HC0')
    # print(hc_number)
    # clusterer = ClusteringMaker(hiercc_results_collection, distance_matrix_collection, 100, 1)
    # clusterer.cluster_members = [1,5,100,110,501]
    # clusterer.retrieve_matrix_from_cluster()
    # clusterer.single_linkage_clustering('test1')
    # cluster = [385, 392, 396, 407, 414, 415, 419, 421, 426, 434, 444, 449, 453, 471, 473, 474, 476, 486, 488, 495, 504, 524, 2607, 2608, 2610, 2613, 2614, 2615, 2616, 2617, 2618, 2619, 2620, 2621, 2622, 2623, 2624, 2625, 2626, 2627, 2628, 2629, 2630, 2632, 2633, 2636, 2638, 2640, 2641, 2642, 2643, 2645, 2646, 2648, 2649, 2650, 2651, 2655, 2656, 2657, 2658, 2662, 2663, 2664, 2665, 2669, 2675, 2676, 2678, 2679, 2680, 2681, 2683, 2684, 2685, 2686, 2687, 2688, 2689, 2692, 2693, 2699, 2700, 2704, 2705, 2711, 2716, 3167, 3170, 3179, 3181, 3182, 3183, 3185, 3186, 3187, 3190, 3193, 3195, 3199, 3200, 3201, 3202, 3203, 3204, 3205, 3206, 3207, 3208, 3209, 3210, 3211, 3213, 3214, 3215, 3216, 3217, 3219, 3220, 3221, 3222, 3223, 3225, 3228, 3229, 7914, 10188, 10190, 10191, 10192, 10193, 10195, 10210, 10212, 10213, 10214, 10215, 10220, 10221, 10222, 10227, 10246, 10375, 10377, 10380, 10382, 10384, 10391, 10400, 10409, 10410, 10418, 10426, 10430, 10433, 10435]
    # compute_matrix=DistanceMatrixComputer(st_collection,cluster_membership_collection,cluster)
    # compute_matrix.compute_hamming_distances('full')
    # print(compute_matrix.hamming_distances[-1])
    # clustering = ClusteringMaker(hiercc_results_collection, isolates_collection, isolateresults_collection, 11, 'S13BD00906')
    # #55 'S14BD05285'
    # #10 'S14BD04971'
    # print(clustering.hamming_distances)
    # print(clustering.cluster_members_samples)
    # clustering.single_linkage_clustering()
    # alternative_clustering = AlternativeClusteringMaker(hiercc_results_collection, isolates_collection,
    #                                                     isolateresults_collection, 7, 'S13BD00906', 10207)
    # alternative_clustering.single_linkage_clustering()
    clustering = ClusteringMakerCustom(cluster_membership_collection,isolates_collection,isolateresults_collection, 7, 'S14BD03397', 'extended_cluster') #extended_cluster split_cluster
    clustering.single_linkage_clustering()