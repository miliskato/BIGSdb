from pymongo import MongoClient
from MongoDB.util.hiercc_cgmlst_profile import HierCCCgMLSTProfile
from MongoDB.util.hiercc_numbers_profile import HierCCNumbersProfile
from MongoDB.util.distance_matrix_computer import DistanceMatrixComputer
from MongoDB.config import HIERCC_CONFIG
import gzip
import subprocess
import logging
import hashlib
from pathlib import Path


class MongoHierCCClustering:
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

    def run_hiercc_clustering(self, st_collection, hiercc_results_collection, distance_matrix_collection) -> int:
        """
        Main function to run the whole clustering using HierCC and storing data in mongoDB
        :param st_collection: the collection of sequence types from mongoDB.
        :param hiercc_results_collection: the collection of hiercc results from mongoDB.
        :param distance_matrix_collection: the collection containing the distance matrix in mongoDB
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
                logging.info(f"Start to process cgmlst profiles for distance computing")
                # self.__compute_distance_matrix(st_collection, distance_matrix_collection)
                # logging.info(f"Running HierCC tool for clustering")
                self.__run_hiercc()
                logging.info(f"Retrieving results from HierCC")
                self.hc_results = self.__retrieve_hiercc_result()
                logging.info(f"Adding HierCC results to the results collection {self.species}")
                self.__add_new_hiercc_numbers(hiercc_results_collection)
                return self.cgmlst_profile.st
            else:
                logging.info(f"Test for missing data failed: cgMLST profile will not be clustered!")
                return None

    def __check_order_of_cgmlst_profile(self, st_collection) -> None:
        db_headers = st_collection.find_one({'ID': 'headers'})['headers']
        if self.cgmlst_profile.loci != db_headers[1:len(db_headers)]:
            bad_headers_map = {}
            for i, b in enumerate(self.cgmlst_profile.loci):
                bad_headers_map[b] = i
            good_indices = [bad_headers_map[a] for a in db_headers[1:len(db_headers)]]
            self.cgmlst_profile.loci = [self.cgmlst_profile.loci[i] for i in good_indices]
            self.cgmlst_profile.cgmlst = [self.cgmlst_profile.cgmlst[j] for j in good_indices]
            if self.cgmlst_profile.loci != db_headers[1:len(db_headers)]:
                raise ValueError('Impossible to get the same cgmlst, issue in the cgmlst profile')

    def __query_sequence_types(self, st_collection) -> int:
        """
        Check if the cgmlst profile from the isolate is already stored in the sequence type collection
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
        Check if the number of missing alleles is not higher than the threshold in order to do the clustering and
        incorporate the results in the database.
        :return:
        """
        missing_alleles = self.cgmlst_profile.cgmlst.count(0)
        proportion_of_missing_alleles = missing_alleles / len(self.cgmlst_profile.cgmlst)
        logging.info(f"Proportion of missing allele is {proportion_of_missing_alleles}")
        if proportion_of_missing_alleles > HIERCC_CONFIG["allowed_missing_data_proportion"]:
            return 'Fail'
        else:
            return 'OK'

    def __add_new_sequence_type(self, st_collection) -> None:
        """
        Add the new sequence type into the sequence type collection and adds also the st to the input file for
        clustering with HierCC.
        :param st_collection: the sequence type collection of mongoDB.
        :return:
        """
        latest_st = st_collection.find_one(sort=[("ST", -1)])
        self.cgmlst_profile.st = latest_st['ST'] + 1
        st_collection.insert_one(self.cgmlst_profile.get_st_collection_entry())
        with gzip.open(HIERCC_CONFIG[self.species]['running_st'], 'at') as f:
            f.write(f'{self.cgmlst_profile.get_st_line_for_hiercc_input()}\n')

    def __compute_distance_matrix(self, st_collection, distance_matrix_collection):
        distance_matrix = DistanceMatrixComputer(st_collection, distance_matrix_collection)
        distance_matrix.compute_hamming_distances('last_st')
        distance_matrix.save_as_hdf5(HIERCC_CONFIG[self.species]["distance_matrix"])

    def __run_hiercc(self) -> None:
        """
        Runs the HierCC clustering tool in command line.
        :return:
        """
        check_file_before_run = hashlib.md5(open(HIERCC_CONFIG[self.species]['npz_file'], 'rb').read()).hexdigest()
        command = f"module load phiercc;" \
                  f" pHierCC -p {HIERCC_CONFIG[self.species]['running_st']} " \
                  f"-a {HIERCC_CONFIG[self.species]['npz_file']} " \
                  f"-o {HIERCC_CONFIG[self.species]['running_clustering'].replace('.HierCC.gz', '')} "
        out = subprocess.run(
            command,
            shell=True,
            executable='/bin/bash')
        check_file_after_run = hashlib.md5(open(HIERCC_CONFIG[self.species]['npz_file'], 'rb').read()).hexdigest()
        if check_file_before_run == check_file_after_run:
            raise RuntimeError("HierCC doesn't seem to have run as the npz file is not changed. Check for exceptions!")

    def __retrieve_hiercc_result(self) -> list:
        """
        Returns the result of the clustering from HierCC
        :return:
        """
        with gzip.open(HIERCC_CONFIG[self.species]['running_clustering'], 'rt') as f:
            return f.readlines()[-1].replace('\n', '').split('\t')

    def __add_new_hiercc_numbers(self, hiercc_results_collection) -> None:
        """
        Adds the HierCC results to the hierCC results collection in mongoDB.
        :param hiercc_results_collection: the hiercc results collection from mongoDB.
        :return:
        """
        hc_headers = hiercc_results_collection.find_one({'ID': 'headers'})['headers']
        self.hc_results = HierCCNumbersProfile(self.hc_results, hc_headers)
        results_to_write = self.hc_results.get_hiercc_results_collection_entries()
        hiercc_results_collection.insert_many(results_to_write)
