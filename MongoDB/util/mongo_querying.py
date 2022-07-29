import abc
import pymongo

class Mongoquerying(object, metaclass=abc.ABCMeta):
    """
    Class containing all queries for Mongo
    """
    def __init__(self):
        pass

    def _query_list_of_all_values(self, opened_collection, variable_of_interest: str = None) -> list:
        """
        Collects all values for a given variable of interest across the entire collection.
        :param opened_collection: mongo opened collection
        :param variable_of_interest: variable to be collected in every document in the collection
        :return:
        """
        return opened_collection.distinct(variable_of_interest)

    def _query_collection(self, opened_collection) -> list:
        """
        Query the entire collection
        :param opened_collection: mongo opened collection
        :return:
        """
        return [doc for doc in opened_collection.find()]

    def _query_docs_by_ids(self, opened_collection, ids: list) -> list:
        """
        Lists the full documents for a given set of ids.
        :param opened_collection: mongo opened collection
        :param ids: list of ids for which the full document is desired
        :return:
        """
        return [doc for doc in opened_collection.find({"_id": {"$in": ids}})]

    def _query_results_by_technicalids(self, opened_isolates_collection, opened_isolateresults_collection,
                                       technicalids: list) -> list:
        """
        Retrieves all latest results for a given set of technical ids in the isolate collection
        :param opened_isolates_collection: mongo opened isolate collection
        :param opened_isolateresults_collection: mongo opened result collection
        :param technicalids: list of technical ids in the isolate collection for whom the latest results should be retrieved in the results collection
        :return:
        """
        return self._query_docs_by_ids(opened_isolateresults_collection,
                                       [doc['latest_results_version'] for doc in self._query_docs_by_ids(opened_isolates_collection,
                                                                                                         technicalids)])
