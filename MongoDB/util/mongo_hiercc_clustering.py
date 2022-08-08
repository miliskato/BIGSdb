from hiercc_cgmlst_profile import HierCCCgMLSTProfile
from hiercc_numbers_profile import HierCCNumbersProfile
from mongo_querying import Mongoquerying
from ..config import HIERCC_CONFIG
import gzip
import os


class MongoHierCCClustering:
    def __init__(self, headers: list, data: list, species: str):
        self.cgmlst_profile = HierCCCgMLSTProfile(data, headers)
        self.hc_results = None
        self.species = species

    def run_hiercc_clustering(self, st_collection, hiercc_results_collection):
        self.cgmlst_profile.st = self.__query_sequence_types()
        if self.cgmlst_profile.st:
            return self.cgmlst_profile.st
        else:
            self.__add_new_sequence_type(st_collection)
            self.__run_hiercc()
            self.hc_results = self.__retrieve_hiercc_result()
            self.__add_new_hiercc_numbers(hiercc_results_collection)
            return self.cgmlst_profile.st

    def __query_sequence_types(self, st_collection) -> str:
        query_st = st_collection.find_one({'cgMLST': self.cgmlst_profile.get_cgmlst_profile()})
        if query_st:
            return query_st['ST']
        else:
            return None

    def __add_new_sequence_type(self, st_collection) -> None:
        latest_st = st_collection.find_one(sort=[("ST", -1)])
        self.cgmlst_profile.st = latest_st + 1
        db_headers = st_collection.find_one({'ID': 'headers'})
        if self.cgmlst_profile.cgmlst == db_headers[1:len(db_headers)]:
            Mongoquerying.write_document(st_collection, self.cgmlst_profile.get_st_collection_entry())
            with gzip.open(HIERCC_CONFIG[self.species]['running_st'], 'wt') as f:
                f.write(f'{self.cgmlst_profile.get_st_line_for_hiercc_input}\n')
        else:
            print('not the same cgmlst order')

    def __run_hiercc(self) -> None:
        command = f"pHierCC -p {HIERCC_CONFIG[self.species]['running_st']} " \
                  f"-a {HIERCC_CONFIG[self.species]['npz_file']}" \
                  f"-o {HIERCC_CONFIG[self.species]['running_clustering']} "
        os.system(command)

    def __retrieve_hiercc_result(self) -> str:
        with gzip.open(HIERCC_CONFIG[self.species]['running_clustering'], 'rt') as f:
            return f.readlines()[-1]

    def __add_new_hiercc_numbers(self, hiercc_results_collection) -> None:
        self.hc_results = HierCCNumbersProfile(self.hc_results)
        results_to_write = self.hc_results.get_hiercc_results_collection_entries()
        for result in results_to_write:
            Mongoquerying.write_document(hiercc_results_collection, result)

