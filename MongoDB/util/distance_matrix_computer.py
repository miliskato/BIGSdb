import logging
import numpy as np
from MongoDB.util.hamming_distance import getDistance, __dist_wrapper, __parallel_dist, hamming_dist
from multiprocessing import Pool
import datetime
from pathlib import Path
import h5py
import fastcluster
from scipy.spatial import distance as ssd
import scipy.cluster.hierarchy as hcluster
from pymongo.write_concern import WriteConcern


class DistanceMatrixComputer:
    """
    Class to compute hamming distances and add them to the distance matrix in mongoDB
    """

    def __init__(self, st_collection, cluster_membership_collection, st_to_use: list):  # distance_matrix_collection,
        """
        Initialize the class
        :param st_collection: sequence type collection from mongoDb
        :param distance_matrix_collection:  distance matrix collection from mongoDB
        :param st_to_use: the list of the sequence types to use or [0]if using all the st of the db
        """
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Initialization of the distance matrix computer")
        self.st_to_use = st_to_use
        self.st_collection = st_collection
        # self.matrix_collection = distance_matrix_collection
        self.cluster_membership_collection = cluster_membership_collection
        self.cgmlst_profiles = []
        self.sequence_types = []
        self.missing_alleles = []
        self.hamming_distances = []
        logging.info("Retrieving cgmlst profiles from the database")
        self.__get_cgmlst_profiles()
        logging.info("Sorting cgmlst profiles")
        self.__sorting_cgmlst_profiles()
        logging.info("Initialization finished!")

    def __get_cgmlst_profiles(self) -> None:
        """
        retrieve all the cgmlst profiles as list from mongoDB st_collection
        :return:
        """
        if self.st_to_use == [0]:
            logging.info("All cgmlst profiles from the db are being retrieved")
            query_all_data = self.st_collection.find({})
        else:
            logging.info("Only the provided st are being retrieved")
            query_or = []
            for st in self.st_to_use:
                query_or.append({'ST': st})
            query_all_data = self.st_collection.find({'$or': query_or})
        for doc in query_all_data:
            if 'ST' in doc:
                self.cgmlst_profiles.append(np.array(doc['cgMLST'].split(',')))
                self.sequence_types.append(doc['ST'])

    def __sorting_cgmlst_profiles(self) -> None:
        """
        sort by ascending order the cgmlst profiles and sequence types
        :return:
        """
        zip_list = zip(self.sequence_types, self.cgmlst_profiles)
        sorted_pairs = sorted(zip_list, reverse=False)
        tuples = zip(*sorted_pairs)
        self.sequence_types, self.cgmlst_profiles = [list(tuple1) for tuple1 in tuples]

    def compute_hamming_distances(self, mode: str) -> None:
        """
        Compute the hamming distances between sequence types
        :param mode: full is to compute all the distances against all the cgmlst in the db while
        last_st computes only for the last sequence types entered in the db.
        :return:
        """
        logging.info(f"{datetime.datetime.now()}: Starting to compute hamming distances in mode {mode}")
        if mode == 'full':
            start = 0
        else:
            start = len(self.cgmlst_profiles) - 1
        pool = Pool(4)
        self.hamming_distances = getDistance(np.array(self.cgmlst_profiles), 'hamming_dist', pool, start)
        logging.info(f"{datetime.datetime.now()}: Hamming distances computed!")

    def init_clustering_and_cluster_membership(self, cluster_thresholds: list) -> None:
        logging.info(f"{datetime.datetime.now()}: Starting initial clustering and clustering membership encoding")
        self.hamming_distances += self.hamming_distances.T
        slc = fastcluster.single(ssd.squareform(self.hamming_distances))
        for thresh in cluster_thresholds:
            cluster_membership = hcluster.fcluster(slc, thresh, criterion='distance')
            documents = []
            for entry in range(len(cluster_membership)):
                doc = {'ST': self.sequence_types[entry],
                       'Threshold': thresh,
                       'Clustering_membership': [int(cluster_membership[entry])]}
                documents.append(doc)
            self.insert_a_lot(documents, self.cluster_membership_collection)
            logging.info(f"{datetime.datetime.now()}: Clustering membership finished for threshold {thresh}")
        logging.info(f"{datetime.datetime.now()}: Clustering and clustering membership finished")

    def _merge_clusters(self, memberships: list, threshold: int) -> int:
        cluster_sizes = []
        print(f'merging clusters {memberships}')
        memberships.sort()
        for cluster in memberships:
            cluster_sizes.append(self.cluster_membership_collection.count_documents({'Threshold': threshold,
                                                                                     'Clustering_membership': cluster}))
        biggest_cluster = max(cluster_sizes)
        max_index = cluster_sizes.index(biggest_cluster)
        new_cluster_name = memberships[max_index]
        clusters_to_rename = [x for i, x in enumerate(memberships) if i != max_index]
        for cl in clusters_to_rename:
            query = {'Threshold': threshold,
                     'Clustering_membership': cl}
            update = {'$set': {'Clustering_membership': new_cluster_name, 'insertion_date': datetime.datetime.utcnow()}}
            self.cluster_membership_collection.update_many(query, update)
        return new_cluster_name

    def new_st_cluster_membership(self, cluster_thresholds: list) -> None:
        for thresh in cluster_thresholds:
            membership = []
            for it in range(len(self.hamming_distances[0]) - 1):
                if self.hamming_distances[0][it] <= thresh:
                    membership.append(self.cluster_membership_collection.find_one({'ST': self.sequence_types[it], 'Threshold': thresh})['Clustering_membership'])
            membership = list(set(membership))
            if len(membership) > 1:
                membership = [self._merge_clusters(membership, thresh)]
            if len(membership) == 0:
                membership.append(self.sequence_types[-1])
            entry = {'ST': self.sequence_types[-1],
                     'insertion_date': datetime.datetime.utcnow(),
                     'Threshold': thresh,
                     'Clustering_membership': membership[0]}
            self.cluster_membership_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(entry)

    def insert_hamming_distances_in_mongo(self):
        """
        inserts the computed hamming distances into mongo Db
        :return:
        """
        if len(self.hamming_distances) == 0:
            print('No distances to insert into the database!')
        else:
            logging.info(f"{datetime.datetime.now()}: Creating and writing distances in mongo Db")
            self.__create_and_write_mongo_entries()
            logging.info(f"{datetime.datetime.now()}: Insertion of distances into the database finished!")

    def __create_and_write_mongo_entries(self):
        hamming_docs_mongo = []
        if len(self.hamming_distances) == 1:
            mode = 'last_st'
        else:
            mode = 'full'
        for i in range(len(self.hamming_distances)):
            for j in range(i):
                if mode == 'full':
                    i_entry = self.sequence_types[i]
                else:
                    i_entry = self.sequence_types[-1]
                hamming_dist_entry = {'I': i_entry,
                                      'J': self.sequence_types[j],
                                      'Hamming_distance': int(self.hamming_distances[i, j])}
                hamming_docs_mongo.append(hamming_dist_entry)
                if len(hamming_docs_mongo) == 100000:
                    self.insert_a_lot(hamming_docs_mongo, self.matrix_collection)
                    hamming_docs_mongo = []  # after writting the object is erased
        self.insert_a_lot(hamming_docs_mongo, self.matrix_collection)

    @staticmethod
    def insert_a_lot(insertion_docs: list, collection) -> None:
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

    def save_as_hdf5(self, hdf_file: Path) -> None:

        if len(self.hamming_distances) == 1:
            with h5py.File(hdf_file, 'a') as file:
                # if mode is last_st for distance computation then the result is added to the existing dataset.
                file['distance_matrix'].resize((file['distance_matrix'].shape[0] + self.hamming_distances.shape[0]),
                                               axis=0)
                file['distance_matrix'][-self.hamming_distances.shape[0]:] = self.hamming_distances

        else:
            file = h5py.File(hdf_file, "w")
            print(self.hamming_distances.shape)
            # if full mode for the computation of the distance matrix, a new dataset is created.
            file.create_dataset('distance_matrix', data=self.hamming_distances,
                                maxshape=(None, self.hamming_distances.shape[1]))
        file.close()
        logging.info(f"{datetime.datetime.now()}: Distance matrix saved as hdf5 at the following location: {hdf_file}")

# import pandas as pd
# from multiprocessing import Pool
# from scipy.spatial import distance as ssd
# from scipy.cluster.hierarchy import linkage
# import scipy.cluster.hierarchy
# import matplotlib
# import plotly
# import fastcluster
# import plotly.figure_factory as ff
# mat = pd.read_csv('/home/bebergk/subset_profiles', sep='\t', header=None, dtype=str).values
# allele_columns = np.array([i == 0 or (not h.startswith('#')) for i, h in enumerate(mat[0])])
# mat = mat[1:, allele_columns]
# start = 0
# pool = Pool(4)
# dist = getDistance(np.array(mat, dtype=np.int32), 'hamming_dist', pool, start)
# dist += dist.T
# slc = linkage(ssd.squareform(dist), method='single')
# test = fastcluster.single(ssd.squareform(dist))
# print(test)
# names = ['ST1','ST2','ST3','ST4','ST5','ST6','ST7','ST8']
# fig = ff.create_dendrogram(test, orientation='left', labels=names, color_threshold=10)
# fig.update_layout(width=800, height=500)
# plotly.offline.plot(fig, filename='file.html')
