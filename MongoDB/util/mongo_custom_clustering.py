from pymongo import MongoClient
from MongoDB.util.hiercc_cgmlst_profile import HierCCCgMLSTProfile
from MongoDB.util.distance_and_cluster_computer import DistanceAndClusterComputer
from MongoDB.config import CLUSTERING_CONFIG
import logging
from pymongo.write_concern import WriteConcern


class MongoCustomClustering:
    def __init__(self, headers: list, data: list, species: str):
        """
        Initialize the class
        :param headers: the headers of the sequence type file from HierCC (so the headers store
        in the sequence type collection of the species).
        :param data: the list of the alleles of the cgmlst profile of the isolate to process.
        :param species: the species of the isolate.
        """
        self.cgmlst_profile = HierCCCgMLSTProfile(data, headers)
        self.hc_results = None
        self.species = species

    def run_custom_clustering(self, st_collection, cluster_membership_collection, cluster_threshold: list) -> int:
        """
        Main function to run the whole clustering and storing data in mongoDB
        :param cluster_threshold: the thresholds for clustering membership to be used for the clustering
        :param st_collection: the collection of sequence types from mongoDB.
        :param cluster_membership_collection: the collection containing the cluster memberships in mongoDB
        :return:
        """
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Check order of the cgMLST profile")
        self.__check_order_of_cgmlst_profile(st_collection)
        logging.info(f"Query sequence type collection for {self.species}")
        self.cgmlst_profile.st = self.__query_sequence_types(st_collection)
        if self.cgmlst_profile.st:
            logging.info(f"Found the sequence type in the sequence type collection of {self.species}")
            return self.cgmlst_profile.st
        else:
            logging.info(f"Test to evaluate if the cgMLST profile doesn't have too many missing data")
            test_missing = self.__check_missing_data()
            if test_missing == 'OK':
                logging.info(f"Test succeeded: the cgMLST profile will be integrated to the sequence type collection "
                             f"from {self.species}")
                self.__add_new_sequence_type(st_collection)
                logging.info(f"Start to process cgmlst profiles for cluster membership computing")
                self.__compute_cluster_membership(st_collection, cluster_membership_collection, cluster_threshold)
                return self.cgmlst_profile.st
            else:
                logging.info(f"Test for missing data failed: cgMLST profile will not be clustered!")
                return None

    def __check_order_of_cgmlst_profile(self, st_collection) -> None:
        """
        Checks if the order of the loci in the st to be added are the same as the one in the st_collection. If not, the,
        it reorder the new st loci to correspond to the order of the st collection.
        :param st_collection: the sequence types collection from mongoDB
        :return:
        """
        try :
            db_headers = st_collection.find_one({'ID': 'headers'})['headers']
        except:
            st_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one({'ID':'headers',
                                      'headers': self.cgmlst_profile.loci})
            db_headers = st_collection.find_one({'ID': 'headers'})['headers']
        if self.cgmlst_profile.loci != db_headers:
            bad_headers_map = {}
            for i, b in enumerate(self.cgmlst_profile.loci):
                bad_headers_map[b] = i
            good_indices = [bad_headers_map[a] for a in db_headers]
            self.cgmlst_profile.loci = [self.cgmlst_profile.loci[i] for i in good_indices]
            self.cgmlst_profile.cgmlst = [self.cgmlst_profile.cgmlst[j] for j in good_indices]
            if self.cgmlst_profile.loci != db_headers:
                raise ValueError('Impossible to get the same cgmlst, issue in the cgmlst profile')

    def __query_sequence_types(self, st_collection) -> int:
        """
        Check if the cgmlst profile from the isolate is already stored in the sequence types collection
        :param st_collection: the sequence type collection from mongo db.
        :return: the sequence type if it exists already in the db or None if it doesn't.
        """
        query_st = st_collection.find_one({'cgMLST': self.cgmlst_profile.get_cgmlst_profile()})
        if query_st:
            return query_st['ST']
        else:
            return None

    def __check_missing_data(self) -> str:
        """
        Checks if the number of missing alleles is not higher than the threshold in order to do the clustering and
        incorporate the results in the database.
        :return:
        """
        missing_alleles = self.cgmlst_profile.cgmlst.count(0)
        proportion_of_missing_alleles = missing_alleles / len(self.cgmlst_profile.cgmlst)
        logging.info(f"Proportion of missing allele is {proportion_of_missing_alleles}")
        if proportion_of_missing_alleles > CLUSTERING_CONFIG["allowed_missing_data_proportion"]:
            return 'Fail'
        else:
            return 'OK'

    def __add_new_sequence_type(self, st_collection) -> None:
        """
        Adds the new sequence type into the sequence types collection.
        :param st_collection: the sequence type collection of mongoDB.
        :return:
        """
        latest_st = st_collection.find_one(sort=[("ST", -1)])
        try:
            self.cgmlst_profile.st = latest_st['ST'] + 1
        except:
            self.cgmlst_profile.st = 1
        st_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(self.cgmlst_profile.get_st_collection_entry())

    def __compute_cluster_membership(self, st_collection, cluster_membership_collection, cluster_threshold: list) ->None:
        """
        Computes the cluster membership for the new sequence added to the st_collection.
        :param st_collection: the sequence types collection from mongoDB.
        :param cluster_membership_collection: the cluster membership collection from mongoDB.
        :param cluster_threshold: The list of thresholds to be applied when clustering the new st and determine its
        clustering membership.
        :return:
        """
        distance_cluster = DistanceAndClusterComputer(st_collection, cluster_membership_collection, [0])
        distance_cluster.compute_hamming_distances('last_st')
        distance_cluster.new_st_cluster_membership(cluster_threshold)

