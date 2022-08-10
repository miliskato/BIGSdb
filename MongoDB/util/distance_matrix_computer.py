from pymongo import MongoClient
from MongoDB.util.mongo_querying import Mongoquerying
import logging

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
        logging.info("Identifying missing alleles in cgmlst profiles")
        self.__get_missing_alleles()
        logging.info("Initialization finished!")

    def __get_cgmlst_profiles(self) -> None:
        """
        retrieve all the cgmlst profiles as list from mongoDB st_collection
        :return:
        """
        query_all_data = self.st_collection.find({})
        for doc in query_all_data:
            if 'ST' in doc:
                self.cgmlst_profiles.append(doc['cgMLST'].split(','))
                self.sequence_types.append(doc['ST'])

    def __sorting_cgmlst_profiles(self) -> None:
        """
        sort by ascending order the cgmlst profiles and sequence types
        :return:
        """
        zip_list = zip(self.sequence_types, self.cgmlst_profiles)
        sorted_pairs = sorted(zip_list, reverse=False)
        tuples = zip(*sorted_pairs)
        self.sequence_types,  self.cgmlst_profiles = [list(tuple1) for tuple1 in tuples]

    def __get_missing_alleles(self) -> None:
        """
        retrieve all the positions in the cgmlst profiles where alleles are zeros in order to skip them for the
        hamming distances.
        :return:
        """
        for cgmlst in self.cgmlst_profiles:
            zeros = [i for i, e in enumerate(cgmlst) if e == 0]
            self.missing_alleles.append(zeros)

    def compute_hamming_distances(self, mode: str) -> None:
        logging.info(f"Starting to compute hamming distances in mode {mode}")
        for i in range(len(self.sequence_types)):
            if mode == 'full':
                range_j = range(i, len(self.sequence_types))
            elif mode == 'last_st':
                range_j = [len(self.sequence_types)-1]
            else:
                raise ValueError('The mode must be in the allowed values: full or last_st')
            for j in range_j:
                hamming_dist = 0
                range_hamming = set(range(len(self.cgmlst_profiles[i]))) - set(self.missing_alleles[i]) \
                                - set(self.missing_alleles[j])
                for h in range_hamming:
                    if self.cgmlst_profiles[i][h] != self.cgmlst_profiles[j][h]:
                        hamming_dist += 1
                hamming_dist_entry = {'I': self.sequence_types[i],
                                      'J': self.sequence_types[j],
                                      'Hamming_distance': hamming_dist}
                self.hamming_distances.append(hamming_dist_entry)
        logging.info(f"Hamming distances computed!")

    def insert_hamming_distances_in_mongo(self):
        if len(self.hamming_distances) == 0:
            print('No distances to insert into the database!')
        else:
            logging.info(f"Inserting distances into the database")
            self.matrix_collection.insert_many(self.hamming_distances)
            logging.info("Insertion of distances into the database finished!")
