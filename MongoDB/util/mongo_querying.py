import abc
import pymongo

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

    def _query_results_by_technicalids(self, opened_isolates_collection, opened_isolateresults_collection,
                                       technicalids: list) -> list:
        """
        Retrieves all latest results for a given set of technical ids in the isolate collection
        :param opened_isolates_collection: mongo opened isolate collection
        :param opened_isolateresults_collection: mongo opened result collection
        :param technicalids: list of technical ids in the isolate collection for whom the latest results should be retrieved in the results collection
        :return: list of lists of latest results of given technical ids
        """
        return self._query_docs_by_ids(opened_isolateresults_collection,
                                       [doc['latest_results_version'] for doc in self._query_docs_by_ids(opened_isolates_collection,
                                                                                                         technicalids)])
    def _query_typing_results_by_technicalids_and_scheme(self, opened_isolates_collection, opened_isolateresults_collection, technicalids: list = ['emptylist'], scheme: str = 'cgmlst'):
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
        for result_index, result in enumerate( self._query_results_by_technicalids(opened_isolates_collection, opened_isolateresults_collection, technicalids)):
            if result_index == 0:
                header = ["isolate_id"]
                for locus in result[scheme]['loci']:
                    header.append(locus['Locus'])
                listofresultlists.append(header)
            # todo change this
            # resultlist = [result['isolates_id']]
            resultlist = [result['_id']]
            for locus in result[scheme]['loci']:
                # todo check logic
                allele_id = locus['Allele_designation']
                if int(allele_id) and locus['Percentage_identity'] == 100.00 and eval(locus['Coverage']) == 1.0:
                    resultlist.append(allele_id)
                else:
                    resultlist.append(0)
            listofresultlists.append(resultlist)
        return listofresultlists