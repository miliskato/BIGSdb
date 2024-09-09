import abc
import logging
import re
import sys
from typing import Any, Dict, List, Union, Optional, Mapping
from copy import deepcopy
from typing import Any, Dict, List, Optional, Union

import pymongo
from pymongo.read_concern import ReadConcern
from .python_utility_functions import convert_dmyhms_to_ymd, merge_nested_dicts


class Mongoquerying(object, metaclass=abc.ABCMeta):
    """
    Class containing all queries for Mongo
    """
    def __init__(self):
        pass

    @staticmethod
    def query_list_of_all_distinct_values(opened_collection: pymongo.collection.Collection,
                                          variable_of_interest: str = '_id', filtering_cond: Optional[Mapping[str, Any]] = None) -> List[str]:
        """
        Collects all values for a given variable of interest across the entire collection.
        :param opened_collection: mongo opened collection
        :param variable_of_interest: variable to be collected in every document in the collection
        :param filtering_cond: Optional: filtering expression for MongoDB
        :return: list of distinct values for a variable of interest
        """
        return opened_collection.distinct(variable_of_interest, filter=filtering_cond)


    @staticmethod
    def query_docs_by_ids(opened_collection: pymongo.collection.Collection, ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Lists the full documents for a given set of ids.
        :param opened_collection: mongo opened collection
        :param ids: list of ids for which the full document is desired
        :return: list of all documents/contents of the in the collection
        """
        if ids:
            return [doc for doc in opened_collection.with_options(read_concern=ReadConcern(level="majority")).find({"_id": {"$in": ids}})]
        else:
            return [doc for doc in opened_collection.with_options(read_concern=ReadConcern(level="majority")).find()]

    def _query_previous_latest_results_by_technicalids(self, opened_isolates_collection: pymongo.collection.Collection,
                                                       opened_isolateresults_collection: pymongo.collection.Collection,
                                                       technicalids: List[str]) -> List[Dict[str, Any]]:
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

    def query_typing_results_by_technicalids_and_scheme(self, opened_isolates_collection: pymongo.collection.Collection,
                                                        opened_headers_collection: pymongo.collection.Collection,
                                                        scheme: str = 'cgmlst', technicalids: Optional[List[str]] = None) -> List[List[Union[str, int]]]:
        """
        Returns a list of lists wherein the first list is the header [isolate, locus1, locus2, ...] and the subsequent lists are the results of all isolates in technical ids
        :param opened_isolates_collection: mongo opened isolate collection
        :param opened_headers_collection: mongo opened headers collection
        :param technicalids: technical ids list, default calculated in function and is all ids
        :param scheme: schemename as string
        :return: List of n lists with first list header and subsesequent lists results of samples
        """
        listofresultlists = []
        for doc_index, doc in enumerate(self.query_docs_by_ids(opened_isolates_collection, technicalids)):
            resultlist = self.singledoc_typing_results_by_technicalids_and_scheme(doc, scheme, opened_headers_collection, doc_index)
            if doc_index == 0:
                # double list with header and first document's results needs to be preserved
                listofresultlists = resultlist
            else:
                # double list serves no use, because it only has one inner list, inner list needs
                # to be appended to the list which contains the list of headers
                listofresultlists.append(resultlist[0])
        return listofresultlists

    @staticmethod
    def singledoc_typing_results_by_technicalids_and_scheme(document: Dict[str, Any], scheme: str, headers_collection: pymongo.collection.Collection, doc_index: int = 0) -> List[List[Union[str, int]]]:
        """

        :param document: document where all results are found under the 'results' key
        :param scheme: Typing scheme of interest
        :param headers_collection: mongo opened headers collection
        :param doc_index: document index if list of documents. If doc_index = 0 will also provide a header
        :return: Either List of 2 lists with first list header and second list; first documents typing allele
        designations OR List of 1 list with only the latter
        """
        listofresultlists = []
        if isinstance(document['results'][scheme]['loci'], list):
            # This is the original input provided by the pipeline
            if doc_index == 0:
                header = ["isolate_id"]
                for locus in document['results'][scheme]['loci']:
                    header.append(locus['Locus'])
                listofresultlists.append(header)
            resultlist = [document['_id']]
            for locus in document['results'][scheme]['loci']:
                allele_id = locus['Allele']
                if locus['% Identity'] == '100.00' and eval(locus['HSP/Locus length']) == 1.0:  # what about possibility to write the eval to the mongodb document, this is not a possibility because then we lose the length information
                    if '_temp_' not in allele_id:
                        if allele_id != '?' and allele_id != '-':
                            resultlist.append(int(allele_id))
                        else:
                            resultlist.append(0)
                    else:
                        resultlist.append(allele_id)
                else:
                    resultlist.append(0)
            listofresultlists.append(resultlist)
            return listofresultlists
        elif isinstance(document['results'][scheme]['loci'], dict):
            # This is the modified list of dicts to dict with list values created by
            # __convert_typinghitdictionaries_to_lists in mainmongo after the consulatancy session
            if doc_index == 0:
                header = ["isolate_id"]
                for locus in sorted(document['results'][scheme]['loci']):
                    header.append(locus)
                listofresultlists.append(header)
            hit_metadata_document = headers_collection.find_one({'type': 'hit_metadata'})
            allele_index = hit_metadata_document[f"{scheme}_loci"].index('Allele')
            identity_index = hit_metadata_document[f"{scheme}_loci"].index('% Identity')
            length_index = hit_metadata_document[f"{scheme}_loci"].index('HSP/Locus length')
            resultlist = [document['_id']]
            for locus in sorted(document['results'][scheme]['loci']):
                allele_id = document['results'][scheme]['loci'][locus][allele_index]
                if document['results'][scheme]['loci'][locus][identity_index] == '100.00' and \
                        eval(document['results'][scheme]['loci'][locus][length_index]) == 1.0:
                    if '_temp_' not in allele_id:
                        if allele_id != '?' and allele_id != '-':
                            resultlist.append(int(allele_id))
                        else:
                            resultlist.append(0)
                    else:
                        resultlist.append(allele_id)
                else:
                    resultlist.append(0)
            listofresultlists.append(resultlist)
            return listofresultlists

    # @staticmethod
    # def adapt_isolates_id_in_mongodb(opened_collection: pymongo.collection.Collection, actual_id: str, new_id: str) -> None:
    #     """
    #     Function to change the _id field of an isolate already upload to MongoDB
    #     :param actual_id: current id of the isolate
    #     :param new_id: new id to give to the isolate
    #     """
    #     var copy = db.isolates_badqc.findOne({_id: 'S17BD00190'})
    #     copy._id = 'S23BDtest'
    #     db.isolates_badqc.insert(copy)

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
    #     :param isolate_collection: the MongoDB collection of isolates
    #     :param hiercc_collection:  the MongoDB collection of hiercc results
    #     :param hc_number: the hc number (starting with HC..) to be retrieved
    #     :return: the hc number of the cluster where the isolates is located.
    #     """
    #     isolate_sequence_type = isolate_collection.with_options(read_concern=ReadConcern(level="majority")).find_one({"_id": isolate_id})['HierCC_ST']
    #     hc_numbers = hiercc_collection.with_options(read_concern=ReadConcern(level="majority")).find({"ST": isolate_sequence_type})
    #     hc_data = HCNumbersData(isolate_sequence_type, hc_numbers)
    #     return hc_data.get_hc_number(hc_number)

    @staticmethod
    def revert_typinghitlists_to_dictionaries(document: Dict[str, Any], headers_collection: pymongo.collection.Collection) -> Dict[str, Any]:
        """
        This function restores the lists of hit metadata (Allele, %id, length etc.) to dictionaries which are more
        easily readable and required for bigsdb
        Be wary, this method does not create a deepcopy, therefore changes are applied to the input docuemnt
        even if the return value's name is modified
        :param document: python dictionary acquired from a mongodb json document
        :param headers_collection: pymongo collection containing the headers for various lists
        :return: The reverted input document
        """
        hit_metadata: Union[None, Dict[str, Union[object, str, List[str]]]] = headers_collection.find_one({'type': 'hit_metadata'})
        if hit_metadata is None:
            # no header so can not revert anything
            return document
        results_to_modify = (document['results'] if 'results' in document else document)  # this is not a deepcopy so results will be modified in document as well
        for mainkey in results_to_modify:  # mainkey is assay or metadata
            if isinstance(results_to_modify[mainkey], dict):
                for subkey in results_to_modify[mainkey]:
                    if subkey == 'loci' and isinstance(results_to_modify[mainkey][subkey], dict):
                        # check whether first locus/results/hits length corresponds to the length of f"{mainkey}_{subkey}"'s value which is the list of headers
                        if f"{mainkey}_{subkey}" in hit_metadata and len(hit_metadata[f"{mainkey}_{subkey}"]) == len(results_to_modify[mainkey][subkey][list(results_to_modify[mainkey][subkey])[0]]):
                            meta_hit_list = []
                            for locus in sorted(results_to_modify[mainkey][subkey].keys()):
                                single_hit_dictionary = {metadata:
                                                         results_to_modify[mainkey][subkey][locus][index]
                                                         for index, metadata in enumerate(hit_metadata[f"{mainkey}_{subkey}"])}
                                single_hit_dictionary['Locus'] = locus
                                meta_hit_list.append(single_hit_dictionary)
                            results_to_modify[mainkey][subkey] = meta_hit_list
        return document

    def get_any_results_version(self, isolate_id: str, searchkey: str, searchvalue: Union[str, int],
                                isolates_collection: pymongo.collection.Collection,
                                old_isolateresults_collection: pymongo.collection.Collection,
                                headers_collection: pymongo.collection.Collection) -> Dict[str, Any]:
        """
        Gets any results version for a given isolate_id
        :param isolate_id: name of the isolate corresponding to the _id key in the isolates collection
        :param searchkey: historic version key, either changed_version or analysis_date
        :param searchvalue: historic key value, int for changed_version, str YYYY-MM-DD for analysis_date
        :param isolates_collection: pymongo main isolates collection
        :param old_isolateresults_collection: pymongo collection of old isolate results
        :param headers_collection: pymongo collection containing the headers for various lists
        :return: document of the requested version
        """
        # 1. Check input
        if searchkey not in ['changed_version', 'analysis_date']:
            raise ValueError(f'Invalid key {searchkey}, key must be changed_version or analysis_date!')
        if searchkey == 'changed_version' and not isinstance(searchvalue, int):
            raise ValueError(f'if changed_version is searchkey; searchvalue must be integer')
        if searchkey == 'analysis_date' and not isinstance(searchvalue, str) and not re.match(r'^\d{4}-\d{2}-\d{2}$', searchvalue):
            raise ValueError(f'if analysis_date is searchkey; searchvalue must be string in YYYY-MM-DD format')
        # 2. Query current results and check whether current results version is the one requested
        current_version = isolates_collection.with_options(read_concern=ReadConcern(level="majority")).find_one({'_id': isolate_id})
        if current_version is None:
            raise Exception(f"No isolate with id '{isolate_id}' could be found in MongoDB.")
        if searchkey == 'changed_version' and current_version['results'][searchkey] <= searchvalue:
            requested_document = current_version
        elif searchkey == 'analysis_date' and convert_dmyhms_to_ymd(current_version['results'][searchkey]) <= searchvalue:
            requested_document = current_version
        # 3. Query all old results up until the requested value, if the requested value is a date,
        # and the date is not an exact date that the sample has a version, the first more recent result will be selected
        else:
            if searchkey == 'changed_version':
                old_versions = old_isolateresults_collection.with_options(read_concern=ReadConcern(level="majority")).\
                    find({'isolates_id': isolate_id, searchkey: {'$gte': searchvalue}})
                old_versions = sorted(old_versions, key=lambda x: convert_dmyhms_to_ymd(x['analysis_date']), reverse=True)
            else:  # key == 'analysis_date'
                old_versions = old_isolateresults_collection.with_options(read_concern=ReadConcern(level="majority")).\
                    find({'isolates_id': isolate_id})
                # sort from most recent to oldest
                old_versions = sorted([x for x in old_versions if convert_dmyhms_to_ymd(x['analysis_date']) >= searchvalue], key=lambda x: convert_dmyhms_to_ymd(x['analysis_date']), reverse=True)
            if len(old_versions) > 0:
                old_versions_merged = old_versions[0]
                if len(old_versions) > 1:
                    for x in old_versions[1:]:
                        merge_nested_dicts(old_versions_merged, x)
                merge_nested_dicts(current_version['results'], old_versions_merged)
            requested_document = current_version
        # 4. Revert the effective dict to list storage to a readable format for the html reporter
        requested_document = self.revert_typinghitlists_to_dictionaries(requested_document, headers_collection)
        requested_document['latest_analysis_date'] = requested_document['results']['analysis_date']
        return requested_document

    @staticmethod
    def retrieve_number_of_old_isolate_results(isolate_id: str, old_isolateresults_collection: pymongo.collection.Collection, validation_type: str) -> int:
        """
        Retrieves the number of old isolate results for a specific isolate_id.
        param old_isolateresults_collection: pymongo collection of old isolate results
        param validation_type: null, bad_quality or resequencing
        return: number of old isolate results for a specific isolate_id
        """
        if validation_type == 'null':
            old_versions = old_isolateresults_collection.with_options(read_concern=ReadConcern(level="majority")). \
                find({'isolates_id': isolate_id})
            old_versions = [x for x in old_versions if x is not None]
            number_of_old_versions = len(old_versions)
        else:
            number_of_old_versions = 0
        return number_of_old_versions
