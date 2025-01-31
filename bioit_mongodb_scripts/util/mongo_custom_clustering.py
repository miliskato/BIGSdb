import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pymongo
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import CLUSTERING_CONFIG
from bioit_mongodb_scripts.util.cgmlst_profile import cgMLSTProfile
from bioit_mongodb_scripts.util.distance_and_cluster_computer import DistanceAndClusterComputer
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, load_config


class MongoCustomClustering:
    def __init__(self, headers: List[str], data: List[Union[str, int]], species: str,
                 naive_clustering_distance_matrix_file: Path,
                 mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Initializes the class
        :param headers: The headers stored in the sequence type collection of the species.
        :param data: the list of the alleles of the cgmlst profile of the isolate to process.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param naive_clustering_distance_matrix_file: The path to the naive clustering cgmlst distance matrix file
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :return: None
        """
        self._cgmlst_profile = cgMLSTProfile(data, headers)
        self._species = species
        self._naive_clustering_distance_matrix_file = naive_clustering_distance_matrix_file
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()
        self._initialize_cluster_index = False
        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_AZURE')
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = \
            self._mongoinit.initialise_clustering_collections()

    def run_custom_clustering(self, cluster_thresholds: List[int]) -> Optional[int]:
        """
        Main function to run the whole clustering and storing data in mongoDB
        :param cluster_thresholds: the thresholds for clustering membership to be used for the clustering
        :return: the cg sequence type if the percentage of missing data does not exceed the threshold, else None
        """
        logging.info("Check order of the cgMLST profile")
        self._check_order_of_cgmlst_profile(self._headers_collection)
        logging.info(f"Query sequence type collection for {self._species}")
        self._cgmlst_profile.st = self._query_sequence_types(self._st_collection)
        logging.info(f"Test to evaluate if the cgMLST profile doesn't have too many missing data")
        if self.__check_missing_data():
            logging.info(f"Test succeeded: the cgMLST profile will be integrated to the sequence type collection "
                         f"from {self._species}")
        else:
            logging.info(f"Test for missing data failed: cgMLST profile will not be clustered!")
            return None
        if self._cgmlst_profile.st:
            logging.info(f"Found the sequence type in the sequence type collection of {self._species}")
            return self._cgmlst_profile.st
        else:
            self._add_new_sequence_type(self._st_collection)
            logging.info(f"Start to process cgmlst profiles for cluster membership computing")
            self._compute_distance_matrix_and_cluster_membership(cluster_thresholds)
            return self._cgmlst_profile.st

    def _check_order_of_cgmlst_profile(self, headers_collection: pymongo.collection.Collection) -> None:
        """
        Checks if the order of the loci in the st to be added are the same as the one in the sequence types collection.
        If not, reorders the new st loci to correspond to the order of the sequence types collection.
        :param headers_collection: the headers collection 
        :return: None
        """
        try:
            db_headers = headers_collection.find_one({'type': 'cgmlst_headers'})['headers']
        except Exception:
            headers_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
                {'type': 'cgmlst_headers',
                 'headers': self._cgmlst_profile.loci})
            self._initialize_cluster_index = True
            db_headers = headers_collection.find_one({'type': 'cgmlst_headers'})['headers']
        if self._cgmlst_profile.loci != db_headers:
            bad_headers_map = {}
            for i, b in enumerate(self._cgmlst_profile.loci):
                bad_headers_map[b] = i
            good_indices = [bad_headers_map[a] for a in db_headers]
            self._cgmlst_profile.loci = [self._cgmlst_profile.loci[i] for i in good_indices]
            self._cgmlst_profile.cgmlst = [self._cgmlst_profile.cgmlst[j] for j in good_indices]
            if self._cgmlst_profile.loci != db_headers:
                raise ValueError('Impossible to get the same cgmlst, issue in the cgmlst profile')

    def _query_sequence_types(self, st_collection: pymongo.collection.Collection) -> Optional[int]:
        """
        Check if the cgmlst profile from the isolate is already stored in the sequence types collection
        :param st_collection: the sequence type collection from MongoDB.
        :return: the sequence type if it exists already in the db or None if it doesn't.
        """
        query_st = st_collection.find_one({'cgMLST': self._cgmlst_profile.cgmlst})
        if query_st:
            return query_st['cgST']
        else:
            return None

    def __check_missing_data(self) -> bool:
        """
        Checks if the number of missing alleles is not higher than the threshold in order to do the clustering and
        incorporate the results in the database.
        :return: boolean which is true if missing data is below limit and false if above limit
        """
        missing_alleles = self._cgmlst_profile.cgmlst.count(0)
        proportion_of_missing_alleles = missing_alleles / len(self._cgmlst_profile.cgmlst)
        logging.info(f"Proportion of missing allele is {proportion_of_missing_alleles}")
        clustering_config = load_config(CLUSTERING_CONFIG)
        if proportion_of_missing_alleles > clustering_config["allowed_missing_data_proportion"]:
            return False
        else:
            return True

    def _add_new_sequence_type(self, st_collection: pymongo.collection.Collection) -> None:
        """
        Adds the new sequence type into the sequence types collection.
        :param st_collection: the sequence type collection of mongoDB.
        :return: None
        """
        latest_st = st_collection.find_one(sort=[("cgST", -1)])
        try:
            self._cgmlst_profile.st = latest_st['cgST'] + 1
        except Exception:
            self._cgmlst_profile.st = 1
        st_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
            self._cgmlst_profile.get_st_collection_entry())

    def _compute_distance_matrix_and_cluster_membership(self, cluster_thresholds: List[int]) -> None:
        """
        Computes the distance matrix and subsequently the cluster membership for the new sequence(s) added to the
        st_collection.
        :param cluster_thresholds: The list of thresholds to be applied when clustering the new st and determine its
        clustering membership.
        :return: None
        """
        distance_cluster = DistanceAndClusterComputer(self._species, self._mongo_config_data)
        cluster_thresholds_not_in_db = []
        for cluster_threshold in cluster_thresholds:
            if not self._cluster_membership_collection.find_one({'threshold': cluster_threshold}):
                cluster_thresholds_not_in_db.append(cluster_threshold)
                cluster_thresholds.remove(cluster_threshold)

        if not self._naive_clustering_distance_matrix_file.is_file():
            hd_np_array = distance_cluster.compute_hamming_distances('full')
            np.save(str(self._naive_clustering_distance_matrix_file), hd_np_array)
        else:
            self.__compute_and_save_distance_matrix_for_last_st(distance_cluster)

            if cluster_thresholds:
                distance_cluster.new_st_cluster_membership(cluster_thresholds)
        if cluster_thresholds_not_in_db:
            # cluster thresholds can have been added to the config, or it could have been a full calculation.
            distance_cluster.init_clustering_and_cluster_membership(set(cluster_thresholds_not_in_db))

        if self._initialize_cluster_index is True:
            self._cluster_membership_collection.create_index([("threshold", 1), ("clustering_membership", 1)])

    def __compute_and_save_distance_matrix_for_last_st(self, distance_cluster: DistanceAndClusterComputer) -> None:
        """
        Computes the update of a new cgst in the database against the existing distance matrix and saves it.
        :param distance_cluster: DistanceAndClusterComputer object
        :return: None
        """
        distance_matrix: np.array = np.load(str(self._naive_clustering_distance_matrix_file))
        hd_np_array = distance_cluster.compute_hamming_distances('last_st')
        # fix the lower triangle to be symmetric
        hd_np_array = np.concatenate([hd_np_array[:, :distance_matrix.shape[0]],
                                      hd_np_array[:, distance_matrix.shape[0]:] +
                                      hd_np_array[:, distance_matrix.shape[0]:].T], axis=1)
        # Add the new distances to the existing matrix
        distance_matrix = np.concatenate([distance_matrix, hd_np_array[:, :distance_matrix.shape[0]]], axis=0)
        distance_matrix = np.concatenate([distance_matrix, hd_np_array.T], axis=1)
        # Save the updated distance matrix
        np.save(str(self._naive_clustering_distance_matrix_file), distance_matrix)
