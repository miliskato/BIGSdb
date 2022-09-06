import abc
import pymongo
import logging
import sys
from MongoDB.util.distance_matrix_query import DistanceMatrixQuery
from MongoDB.util.hcnumbers_data import HCNumbersData


class Mongoquerying(object, metaclass=abc.ABCMeta):
    """
    Class containing all queries for Mongo
    """

    def __init__(self):
        pass

    def _query_list_of_all_distinct_values(self, opened_collection, variable_of_interest: str = '_id') -> list:
        """
        Collects all values for a given variable of interest across the entire collection.
        :param opened_collection: mongo opened collection
        :param variable_of_interest: variable to be collected in every document in the collection
        :return: list of distinct values for a variable of interest
        """
        return opened_collection.distinct(variable_of_interest)

    def _query_collection(self, opened_collection) -> list:
        """
        Query the entire collection
        :param opened_collection: mongo opened collection
        :return: list of all documents/contents in the collection
        """
        return [doc for doc in opened_collection.find()]

    def _query_docs_by_ids(self, opened_collection, ids: list) -> list:
        """
        Lists the full documents for a given set of ids.
        :param opened_collection: mongo opened collection
        :param ids: list of ids for which the full document is desired
        :return: list of all documents/contents of the in the collection
        """
        return [doc for doc in opened_collection.find({"_id": {"$in": ids}})]

    def _query_previous_latest_results_by_technicalids(self, opened_isolates_collection,
                                                       opened_isolateresults_collection,
                                                       technicalids: list) -> list:
        """
        Retrieves all latest results for a given set of technical ids in the isolate collection
        :param opened_isolates_collection: mongo opened isolate collection
        :param opened_isolateresults_collection: mongo opened result collection
        :param technicalids: list of technical ids in the isolate collection for whom the latest results should be retrieved in the results collection
        :return: list of lists of latest results of given technical ids
        """
        return self._query_docs_by_ids(opened_isolateresults_collection,
                                       [doc['previous_latest_results_version'] for doc in
                                        self._query_docs_by_ids(opened_isolates_collection,
                                                                technicalids)])

    def _query_typing_results_by_technicalids_and_scheme(self, opened_isolates_collection, scheme: str = 'cgmlst',
                                                         technicalids: list = ['emptylist']):
        """
        Returns a list of lists wherein the first list is the header [isolate, locus1, locus2, ..] and the subsequent lists are the results of all isolates in technical ids
        :param opened_isolates_collection: mongo opened isolate collection
        :param opened_isolateresults_collection: mongo opened isolateresults collection belonging to isolate collection
        :param technicalids: technical ids list, default calculated in function and is all ids
        :param scheme: schemename as string
        :return: list of lists of allele designations
        """
        if technicalids == ['emptylist']:
            technicalids = self._query_list_of_all_distinct_values(opened_isolates_collection, "_id")
        listofresultlists = []
        for doc_index, doc in enumerate(self._query_docs_by_ids(opened_isolates_collection, technicalids)):
            if doc_index == 0:
                header = ["isolate_id"]
                for locus in doc['results'][scheme]['loci']:
                    header.append(locus['Locus'])
                listofresultlists.append(header)
            resultlist = [doc['_id']]
            for locus in doc['results'][scheme]['loci']:
                # todo check logic
                allele_id = locus['Allele_designation']
                if isinstance(allele_id, int) and locus['Percentage_identity'] == 100.00 and eval(
                        locus['Coverage']) == 1.0:
                    resultlist.append(allele_id)
                else:
                    resultlist.append(0)
            listofresultlists.append(resultlist)
        return listofresultlists

    def write_document(self, opened_collection, json_input: dict):
        """
        write a document into a collection.
        :param opened_collection: the collection where the document needs to be saved
        :param json_input: the document to store into the collection
        :return:
        """
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
        collection_write = opened_collection.insert_one(json_input)
        logging.debug(f"Writing {collection_write.inserted_id} in collection {opened_collection}")
        return collection_write.inserted_id

    def find_isolates_cgmlst_distance(self, isolate_id: str, distance_threshold: int, isolate_collection,
                                      distance_matrix_collection) -> list:
        isolate_sequence_type = isolate_collection.find_one({"_id": isolate_id})['HierCC_cgST']
        distance_query = DistanceMatrixQuery(isolate_id, isolate_sequence_type, distance_threshold,
                                             distance_matrix_collection)
        st_under_threshold = distance_query.run_distance_query()
        sample_id_below_threshold = []
        for st in st_under_threshold:
            query = isolate_collection.find({'HierCC_cgST': st})
            for result in query:
                sample_id_below_threshold.append(result['_id'])
        return sample_id_below_threshold

    def find_HC_numbers_for_isolate(self, isolate_id: str, isolate_collection, hiercc_collection,
                                    hc_number: str) -> int:
        """
        query to retrieve a specific hc number from an isolate
        :param isolate_id: the id from the desired isolate
        :param isolate_collection: the mongo db collection of isolates
        :param hiercc_collection:  the mongo db collection of hiercc results
        :param hc_number: the hc number (starting with HC..) to be retrieved
        :return: the hc number of the cluster where the isolates is located.
        """
        isolate_sequence_type = isolate_collection.find_one({"_id": isolate_id})['HierCC_ST']
        hc_numbers = hiercc_collection.find({"ST": isolate_sequence_type})
        hc_data = HCNumbersData(isolate_sequence_type, hc_numbers)
        return hc_data.get_hc_number(hc_number)
