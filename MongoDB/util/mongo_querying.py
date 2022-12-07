import abc
import pymongo
import logging
import sys
from pymongo.read_concern import ReadConcern
from copy import deepcopy


class Mongoquerying(object, metaclass=abc.ABCMeta):
    """
    Class containing all queries for Mongo
    """

    def __init__(self):
        pass

    def query_list_of_all_distinct_values(self, opened_collection: object, variable_of_interest: str = '_id') -> list:
        """
        Collects all values for a given variable of interest across the entire collection.
        :param opened_collection: mongo opened collection
        :param variable_of_interest: variable to be collected in every document in the collection
        :return: list of distinct values for a variable of interest
        """
        return opened_collection.distinct(variable_of_interest)

    def _query_collection(self, opened_collection: object) -> list:
        """
        Query the entire collection
        :param opened_collection: mongo opened collection
        :return: list of all documents/contents in the collection
        """
        return [doc for doc in opened_collection.with_options(read_concern=ReadConcern(level="majority")).find()]

    def query_docs_by_ids(self, opened_collection: object, ids: list) -> list:
        """
        Lists the full documents for a given set of ids.
        :param opened_collection: mongo opened collection
        :param ids: list of ids for which the full document is desired
        :return: list of all documents/contents of the in the collection
        """
        return [doc for doc in opened_collection.with_options(read_concern=ReadConcern(level="majority")).find({"_id": {"$in": ids}})]

    def _query_previous_latest_results_by_technicalids(self, opened_isolates_collection: object,
                                                       opened_isolateresults_collection: object,
                                                       technicalids: list) -> list:
        """
        Retrieves all latest results for a given set of technical ids in the isolate collection
        :param opened_isolates_collection: mongo opened isolate collection
        :param opened_isolateresults_collection: mongo opened result collection
        :param technicalids: list of technical ids in the isolate collection for whom the latest results should be retrieved in the results collection
        :return: list of lists of latest results of given technical ids
        """
        return self.query_docs_by_ids(opened_isolateresults_collection,
                                      [doc['previous_latest_results_document'] for doc in
                                       self.query_docs_by_ids(opened_isolates_collection,
                                                              technicalids)])

    def _query_typing_results_by_technicalids_and_scheme(self, opened_isolates_collection: object, scheme: str = 'cgmlst',
                                                         technicalids: list = ['emptylist']) -> list:
        """
        Returns a list of lists wherein the first list is the header [isolate, locus1, locus2, ..] and the subsequent lists are the results of all isolates in technical ids
        :param opened_isolates_collection: mongo opened isolate collection
        :param technicalids: technical ids list, default calculated in function and is all ids
        :param scheme: schemename as string
        :return: list of lists of allele designations
        """
        if technicalids == ['emptylist']:
            technicalids = self.query_list_of_all_distinct_values(opened_isolates_collection, "_id")
        listofresultlists = []
        for doc_index, doc in enumerate(self.query_docs_by_ids(opened_isolates_collection, technicalids)):
            if doc_index == 0:
                header = ["isolate_id"]
                for locus in doc['results'][scheme]['loci']:
                    header.append(locus['Locus'])
                listofresultlists.append(header)
            resultlist = [doc['_id']]
            for locus in doc['results'][scheme]['loci']:
                # todo check logic
                allele_id = locus['Allele']
                if locus['% Identity'] == '100.00' and eval(locus['HSP/Locus length']) == 1.0:
                    if 'Temp_' not in allele_id:
                        if allele_id != '?' and allele_id != '-':
                            resultlist.append(int(allele_id))
                        else:
                            print('weird case of interrogation 100 percent')
                            resultlist.append(0)

                    else:
                        resultlist.append(allele_id)
                else:
                    resultlist.append(0)
            listofresultlists.append(resultlist)
        return listofresultlists

    def write_document(self, opened_collection: object, json_input: dict) -> str:
        """
        write a document into a collection.
        :param opened_collection: the collection where the document needs to be saved
        :param json_input: the document to store into the collection
        :return: id of inserted document (either pre-given in json_input or auto-generated by Mongo)
        """
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
        collection_write = opened_collection.insert_one(json_input)
        logging.debug(f"Writing {collection_write.inserted_id} in collection {opened_collection}")
        return collection_write.inserted_id

    # def find_isolates_cgmlst_distance(self, isolate_id: str, distance_threshold: int, isolate_collection,
    #                                   distance_matrix_collection) -> list:
    #     isolate_sequence_type = isolate_collection.with_options(read_concern=ReadConcern(level="majority")).find_one({"_id": isolate_id})['HierCC_cgST']
    #     distance_query = DistanceMatrixQuery(isolate_id, isolate_sequence_type, distance_threshold,
    #                                          distance_matrix_collection)
    #     st_under_threshold = distance_query.run_distance_query()
    #     sample_id_below_threshold = []
    #     for st in st_under_threshold:
    #         query = isolate_collection.with_options(read_concern=ReadConcern(level="majority")).find({'HierCC_cgST': st})
    #         for result in query:
    #             sample_id_below_threshold.append(result['_id'])
    #     return sample_id_below_threshold
    #
    # def find_HC_numbers_for_isolate(self, isolate_id: str, isolate_collection, hiercc_collection,
    #                                 hc_number: str) -> int:
    #     """
    #     query to retrieve a specific hc number from an isolate
    #     :param isolate_id: the id from the desired isolate
    #     :param isolate_collection: the mongo db collection of isolates
    #     :param hiercc_collection:  the mongo db collection of hiercc results
    #     :param hc_number: the hc number (starting with HC..) to be retrieved
    #     :return: the hc number of the cluster where the isolates is located.
    #     """
    #     isolate_sequence_type = isolate_collection.with_options(read_concern=ReadConcern(level="majority")).find_one({"_id": isolate_id})['HierCC_ST']
    #     hc_numbers = hiercc_collection.with_options(read_concern=ReadConcern(level="majority")).find({"ST": isolate_sequence_type})
    #     hc_data = HCNumbersData(isolate_sequence_type, hc_numbers)
    #     return hc_data.get_hc_number(hc_number)

    def query_failed_causes(self, isolates_badqc_collection: object) -> print():
        """
        aggregation pipeline to collect which qc check status is 'Failed' the most often
        :param isolates_badqc_collection: bad quality samples collection
        :return: prints the qc checks and the number of times theyre failed across the entire bad qc collection
        """
        random_doc = isolates_badqc_collection.find_one()
        for k in random_doc['results']['qc'].keys():
            for key in random_doc['results']['qc'][k].keys():
                if key.endswith('status'):
                    keystring = f"$results.qc.{k}.{key}"
                    status_dict = {}
                    for x in isolates_badqc_collection.aggregate(
                            [{"$group": {"_id": f"{keystring}", "count": {"$sum": 1}}}]):
                        status_dict[x['_id']] = x['count']
                    if 'Failed' in status_dict.keys():
                        print("{}\t{}".format(key,
                                              round((int(status_dict['Failed']) / sum(status_dict.values()) * 100), 1)))
                    else:
                        print("{}\t{}".format(key, 0))

    def query_what_changed_compared_to_previous(self, isolate_id: str, isolates_collection: object, isolateresults_collection: object) -> logging:
        """
        query what changed compared to previous version of isolate results
        :param isolate_id: isolate name
        :param isolates_collection:
        :param isolateresults_collection:
        :return: log with changes if any
        """
        # no checks are done to see if exists
        new_results = isolates_collection.find_one({'results.isolates_id': isolate_id})['results']
        old_results = isolateresults_collection.find_one({'isolates_id': isolate_id, 'changed_version': new_results['changed_version'] - 1})
        for mainkey in new_results.keys():
            if isinstance(new_results[mainkey], dict):
                for subkey in new_results[mainkey].keys():
                    if mainkey not in old_results.keys():
                        logging.info(f"{mainkey} not in old results")
                    elif subkey == 'loci' or subkey == 'results' or subkey.startswith('hits'):
                        if subkey not in old_results[mainkey].keys() or new_results[mainkey][subkey] != \
                                old_results[mainkey][subkey]:
                            # keep in mind that loci is a list: it seems as if loci are always outputted in the same order though so that is allright
                            logging.info(f"{mainkey}{subkey} different or not in old")
                            logging.info(f"from old '{[x for x in old_results[mainkey][subkey] if x not in new_results[mainkey][subkey]]}' was/were removed or changed to '{[x for x in new_results[mainkey][subkey] if x not in old_results[mainkey][subkey]]}'")

    def query_old_results_and_replace_pointers(self, isolateresults_collection: object, old_results_doc_with_pointers: dict) -> dict:
        old_results_doc_without_pointers = deepcopy(old_results_doc_with_pointers)
        if old_results_doc_without_pointers.get('results'):
            raise Exception('Not an old results document')
        pointers_list = []
        for key in old_results_doc_without_pointers:
            if type(old_results_doc_without_pointers[key]) == dict and old_results_doc_without_pointers[key].get('pointer'):
                pointers_list.append(old_results_doc_without_pointers[key]['pointer'])
        pointers_list_unique = list(set(pointers_list))
        if len(pointers_list_unique) > 0:
            old_docs_containing_results_list = self.query_docs_by_ids(isolateresults_collection, pointers_list_unique)
            if len(pointers_list_unique) != len(old_docs_containing_results_list):
                raise Exception('Documents are missing from the old results database')
            # transform old_docs list to dict:
            old_docs_containing_results_dict = {document['_id']:document for document in old_docs_containing_results_list}
            for key in old_results_doc_without_pointers:
                if type(old_results_doc_without_pointers[key]) == dict and old_results_doc_without_pointers[key].get('pointer'):
                    results_dict = old_docs_containing_results_dict[old_results_doc_without_pointers[key]['pointer']][key]
                    # update informs_tools, informs_dbs, and analysis_date with current ones
                    # results_dict.update(old_results_doc_with_pointers[key])
                    # results_dict.pop('pointer')
                    old_results_doc_without_pointers[key] = results_dict  # which is now without pointers
        return old_results_doc_without_pointers  # which is now without pointers
