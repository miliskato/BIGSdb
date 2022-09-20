import logging
import numpy as np
from MongoDB.util.hamming_distance import getDistance, __dist_wrapper, __parallel_dist, hamming_dist
from multiprocessing import Pool
from datetime import datetime

class DistanceMatrixComputer:
    """
    Class to compute hamming distances and add them to the distance matrix in mongoDB
    """

    def __init__(self, st_collection, distance_matrix_collection):
        """
        Initialize the class
        :param st_collection: sequence type collection from mongoDb
        :param distance_matrix_collection:  distance matrix collection from mongoDB
        """
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Initialization of the distance matrix computer")
        self.st_collection = st_collection
        self.matrix_collection = distance_matrix_collection
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
        query_all_data = self.st_collection.find({})
        for doc in query_all_data:
            if 'ST' in doc:
                self.cgmlst_profiles.append(np.array(doc['cgMLST'].split(','), dtype=np.int32))
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
        logging.info(f"{datetime.now()}: Starting to compute hamming distances in mode {mode}")
        if mode == 'full':
            start = 0
        else:
            start = len(self.cgmlst_profiles) - 1
        pool = Pool(4)
        self.hamming_distances = getDistance(np.array(self.cgmlst_profiles), 'hamming_dist', pool, start)
        logging.info(f"{datetime.now()}: Hamming distances computed!")

    def insert_hamming_distances_in_mongo(self):
        """
        inserts the computed hamming distances into mongo Db
        :return:
        """
        if len(self.hamming_distances) == 0:
            print('No distances to insert into the database!')
        else:
            logging.info(f"{datetime.now()}: Creating and writing distances in mongo Db")
            self.__create_and_write_mongo_entries()
            logging.info(f"{datetime.now()}: Insertion of distances into the database finished!")

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
                                      'Hamming_distance': int(self.hamming_distances[i,j])}
                hamming_docs_mongo.append(hamming_dist_entry)
                if len(hamming_docs_mongo) == 100000:
                    self.insert_a_lot(hamming_docs_mongo, self.matrix_collection)
                    hamming_docs_mongo = [] #after writting the object is erased
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