import yaml
import logging
import sys
from util.mongo_querying import Mongoquerying
from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG
from config import HIERCC_CONFIG
from util.hiercc_data import HierCCData
from util.hiercc_cgmlst_profile import HierCCCgMLSTProfile
from util.hiercc_numbers_profile import HierCCNumbersProfile
from MongoDB.util.distance_matrix_computer import DistanceMatrixComputer

def write_headers(headers: list, collection) -> None:
    document = {'ID': 'headers', 'headers': headers}
    Mongoquerying.write_document(collection, document)

def write_st_data(data: list, collection) -> None:
    st_entries = []
    for entry in data:
        cgmlst_profile = HierCCCgMLSTProfile(entry)
        st_entries.append(cgmlst_profile.get_st_collection_entry())
    DistanceMatrixComputer.insert_a_lot(st_entries, collection)

def write_hc_data(data: list, headers: list, collection) -> None:
    for hc_entry in data:
        hc_profile = HierCCNumbersProfile(hc_entry, headers)
        hc_docs = hc_profile.get_hiercc_results_collection_entries()
        collection.insert_many(hc_docs)

if __name__ == '__main__':
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Open collections
    mongoinit = Mongoinitialisation()
    mongoquerying = Mongoquerying()
    #listeria collection
    st_collection, hiercc_results_collection, distance_matrix_collection =\
        mongoinit.initialise_hiercc_collections(config_data, 'listeria')
    #enter st collection
    listeria_st_data = HierCCData(HIERCC_CONFIG['listeria']['initial_st'])
    write_headers(listeria_st_data.header, st_collection)
    write_st_data(listeria_st_data.data, st_collection)
    # enter hiercc results collection
    listeria_hc_data = HierCCData(HIERCC_CONFIG['listeria']['initial_clustering'])
    write_headers(listeria_hc_data.header, hiercc_results_collection)
    write_hc_data(listeria_hc_data.data, listeria_hc_data.header, hiercc_results_collection)
    """
    Under Development
    """
    #compute distances from the cgmlst profiles
    # listeria_dist_mat = DistanceMatrixComputer(st_collection, distance_matrix_collection)
    # listeria_dist_mat.compute_hamming_distances('full')
    # listeria_dist_mat.insert_hamming_distances_in_mongo()






