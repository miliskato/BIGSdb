import datetime
import logging
import sys
from multiprocessing import Pool
from typing import Any, Dict, List
from pathlib import Path

import fastcluster
import numpy as np
import pymongo
import scipy.cluster.hierarchy as hcluster
from pymongo.write_concern import WriteConcern
from scipy.spatial import distance as ssd

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.hamming_distance import get_distance
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


class DistanceAndClusterComputer:
    """
    Class to compute hamming distances and determine the cluster membership to store in mongoDB.
    """

    def __init__(self, species: str, mongo_config_data: Dict[str, Any] = None, st_to_use: List[int] = None) -> None:
        """
        Initializes the class.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :param st_to_use: sequence types list to be used for clustering
        :return: None
        """
        self._species = species
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()
        self._st_to_use = st_to_use
        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data)
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = self._mongoinit. \
            initialise_clustering_collections()
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()
        logging.info("Initialization of the distance and cluster computer")
        self._cgmlst_profiles = []
        self._sequence_types = []
        self._hamming_distances = []
        logging.info("Retrieving cgmlst profiles from the database")
        self._get_cgmlst_profiles()
        logging.info("Sorting cgmlst profiles")
        self._sorting_cgmlst_profiles()
        logging.info("Initialization finished!")

    def _get_cgmlst_profiles(self) -> None:
        """
        Retrieves all the cgmlst profiles as list from mongoDB st_collection.
        :return:
        """
        if not self._st_to_use:
            logging.info("All cgmlst profiles from the db are being retrieved")
            query_all_data = self._st_collection.find({})
        else:
            logging.info("Only the provided st are being retrieved")
            query_all_data = self._st_collection.find({'cgST': {'$in': self._st_to_use}})

        for doc in list(query_all_data):
            if 'cgST' in doc:
                self._cgmlst_profiles.append(np.array(doc['cgMLST']))
                self._sequence_types.append(doc['cgST'])

    def _sorting_cgmlst_profiles(self) -> None:
        """
        Sorts by ascending order the cgmlst profiles and sequence types.
        :return:
        """
        zip_list = zip(self._sequence_types, self._cgmlst_profiles)
        sorted_pairs = sorted(zip_list, reverse=False)
        tuples = zip(*sorted_pairs)
        self._sequence_types, self._cgmlst_profiles = [list(tuple1) for tuple1 in tuples]

    def compute_hamming_distances(self, mode: str) -> None:
        """
        Computes the hamming distances between sequence types
        :param mode: full is to compute all the distances against all the cgmlst in the db while
        last_st computes only for the last sequence type entered in the db.
        :return:
        """
        logging.info(f"{datetime.datetime.now()}: Starting to compute hamming distances in mode {mode}")
        if mode == 'full':
            start = 0
        elif mode == 'last_st':
            start = len(self._cgmlst_profiles) - 1
        else:
            raise ValueError('mode should be either full or last_st for compute_hamming_distances')
        pool = Pool(4)
        self._hamming_distances = get_distance(np.array(self._cgmlst_profiles), 'hamming_dist', pool, start=start, mongo_config_data=self._mongo_config_data)
        if mode == 'full':
            # when mode is full, half matrix is computed (lower triangle) so as we know that the
            # distances are symetric we can add the transposed to retrieve the upper triangle of the matrix
            # and get a squared distance matrix for downstream applications
            self._hamming_distances += self._hamming_distances.T
        logging.info(f"{datetime.datetime.now()}: Hamming distances computed!")

    def init_clustering_and_cluster_membership(self, cluster_thresholds: set) -> None:
        """
        This function is to compute the clustering from more than one sequence type. It uses the distance matrix and
        after clustering (single-linkage) it determines for every ST the cluster membership of all the ST for every
        distance threshold.
        :param cluster_thresholds: the list of cluster thresholds to be used to determine the cluster membership of
        the different st.
        :return:
        """
        logging.info(f"{datetime.datetime.now()}: Starting initial clustering and clustering membership encoding")
        slc = fastcluster.single(ssd.squareform(self._hamming_distances))
        for thresh in cluster_thresholds:
            cluster_membership = hcluster.fcluster(slc, thresh, criterion='distance')
            documents = []
            for entry in range(len(cluster_membership)):
                doc = {'cgST': self._sequence_types[entry],
                       'insertion_date': datetime.datetime.utcnow(),
                       'threshold': thresh,
                       'clustering_membership': int(cluster_membership[entry])}
                documents.append(doc)
            self._insert_a_lot(documents, self._cluster_membership_collection)
            logging.info(f"{datetime.datetime.now()}: Clustering membership finished for threshold {thresh}")
        logging.info(f"{datetime.datetime.now()}: Clustering and clustering membership finished")

    def _merge_clusters(self, memberships: list, threshold: int) -> int:
        """
        A function used to merge clusters and recompute the cluster memberships from the st of the older clusters that
        were merged.
        :param memberships: a list of the cluster membership of the st that belong to more than one cluster (merging
        of the clusters is thus required).
        :param threshold: The threshold of clustering for which those memberships belong to. (e.g. clustering was
        carried out at 7 alleles of difference => threshold is 7).
        :return:
        """
        cluster_sizes = []
        logging.debug(f'merging clusters {memberships}')
        memberships.sort()
        for cluster in memberships:
            cluster_sizes.append(self._cluster_membership_collection.count_documents({'threshold': threshold,
                                                                                     'clustering_membership': cluster}))
        max_index = cluster_sizes.index(max(cluster_sizes))
        new_cluster_name = memberships[max_index]
        clusters_to_rename = [x for i, x in enumerate(memberships) if i != max_index]
        for cl in clusters_to_rename:
            query = {'threshold': threshold,
                     'clustering_membership': cl}
            self.__save_cluster_membership_in_history(query, new_cluster_name, threshold)
            update = {'$set': {'clustering_membership': new_cluster_name, 'insertion_date': datetime.datetime.utcnow()}}
            self._cluster_membership_collection.update_many(query, update)
        return new_cluster_name

    def __save_cluster_membership_in_history(self, query: dict, new_cluster_name: int, thresh: int) -> None:
        """
        Saves in the cluster merging collection the record of a merging of cluster for each cgST that were in the older
        cluster.
        :param query: the query to retrieve all the cgST from this particular cluster.
        :param new_cluster_name: the new cluster names that the cgST will belong to.
        :param thresh: the threshold for which the merging occurs.
        :return: None
        """
        query_res = self._cluster_membership_collection.find(query)
        for st in query_res:
            self._cluster_merging_collection.insert_one({'cgST': st['cgST'],
                                                         'threshold': thresh,
                                                         'merging_date': datetime.datetime.utcnow(),
                                                         'old_cluster': st['clustering_membership'],
                                                         'new_cluster': new_cluster_name})

    def new_st_cluster_membership(self, cluster_thresholds: list) -> None:
        """
        Determines the cluster membership of the new st which is being clustered and stores it into mongoDB.
        :param cluster_thresholds: The list of thresholds to be used for the clustering.
        :return:
        """
        for thresh in cluster_thresholds:
            membership = []
            for it in range(len(self._hamming_distances[0]) - 1):
                if self._hamming_distances[0][it] <= thresh:
                    membership.append(self._cluster_membership_collection.find_one({'cgST': self._sequence_types[it],
                                                                                    'threshold': thresh})['clustering_membership'])
            membership = list(set(membership))
            if len(membership) > 1:
                membership = [self._merge_clusters(membership, thresh)]
            elif len(membership) == 0:
                membership.append(self._sequence_types[-1])
            entry = {'cgST': self._sequence_types[-1],
                     'insertion_date': datetime.datetime.utcnow(),
                     'threshold': thresh,
                     'clustering_membership': membership[0]}
            self._cluster_membership_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(entry)

    @staticmethod
    def _insert_a_lot(insertion_docs: list, collection: pymongo.collection.Collection) -> None:
        """
        In order to avoid having the bug of too many elements in the insertion, this function takes the list of
        elements to insert into mongo db and creates smaller batches of insertion that will be inserted into mongoDB
        :param insertion_docs: the list of all the docs to insert into mongoDB
        :param collection: the collection of MongoDB where to insert the docs.
        :return:
        """
        n = 10000  # batch size of the insert
        batch_list = [insertion_docs[i:i + n] for i in range(0, len(insertion_docs), n)]
        for batch in batch_list:
            collection.insert_many(batch)
