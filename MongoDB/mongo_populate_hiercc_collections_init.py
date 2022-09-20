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
from MongoDB.util.cgmlst_profiles_downloader import CgMLSTProfilesDownloader
import sys, gzip, logging, click


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


def create_i_j_indexes(collection) -> None:
    collection.create_index('I')
    collection.create_index('J')


if __name__ == '__main__':
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    #species = ['listeria', 'mycobacterium', 'neisseria', 'salmonella', 'stec']
    species = ['mycobacterium']
    # Open collections
    mongoinit = Mongoinitialisation()
    mongoquerying = Mongoquerying()
    for sp in species:
        st_collection, hiercc_results_collection, distance_matrix_collection = \
            mongoinit.initialise_hiercc_collections(config_data, sp)
        #initialize the profile file for hiercc
        CgMLSTProfilesDownloader.download_cgmlst_profiles(HIERCC_CONFIG[sp]['download_st'],
                                                          HIERCC_CONFIG[sp]['initial_st'])
        CgMLSTProfilesDownloader.format_profile_gz(HIERCC_CONFIG[sp]['initial_st'])
        # enter st collection
        # species_st_data = HierCCData(HIERCC_CONFIG[sp]['initial_st'])
        # write_headers(species_st_data.header, st_collection)
        # write_st_data(species_st_data.data, st_collection)
        # # compute distances from the cgmlst profiles
        # species_dist_mat = DistanceMatrixComputer(st_collection, distance_matrix_collection)
        # species_dist_mat.compute_hamming_distances('full')
        # species_dist_mat.insert_hamming_distances_in_mongo()
        # create_i_j_indexes(distance_matrix_collection)
        # # enter hiercc results collection
        # species_hc_data = HierCCData(HIERCC_CONFIG[sp]['initial_clustering'])
        # write_headers(species_hc_data.header, hiercc_results_collection)
        # write_hc_data(species_hc_data.data, species_hc_data.header, hiercc_results_collection)
