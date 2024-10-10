import abc
import re
from typing import Any, Dict, List, Optional, Union
from typing import Mapping

import pymongo
from pymongo.read_concern import ReadConcern

from .python_utility_functions import convert_dmyhms_to_ymd, merge_nested_dicts, merge_mongo_dicts
from ..model.json_model import MongoRecordDict, JsonReportDict


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

    @staticmethod
    def singledoc_typing_results_by_technicalids_and_scheme(json_report: JsonReportDict, isolate: str, scheme: str, headers_collection: pymongo.collection.Collection, doc_index: int = 0) -> List[List[Union[str, int]]]:
        """
        Return data required for clustering purpose: [optional(headers (locus names) from the scheme), corresponding alleles found in the given isolate]
        :param json_report: json dict containing all results which are found under the 'results' key
        :param isolate: str corresponding to the isolate name stored in _id from mongo isolates collection
        :param scheme: Typing scheme of interest
        :param headers_collection: mongo opened headers collection
        :param doc_index: document index if list of documents. If doc_index = 0 will also provide a header
        :return: Either List of 2 lists with first list header and second list; first documents typing allele
        designations OR List of 1 list with only the latter
        """

        scheme_loci = json_report[scheme]['loci']

        if isinstance(scheme_loci, list):
            return Mongoquerying._create_scheme_profile_from_json(doc_index, isolate, scheme_loci)
        elif isinstance(scheme_loci, dict):
            return Mongoquerying._create_scheme_profile_from_mongo(doc_index, headers_collection, isolate, scheme, scheme_loci)

    @staticmethod
    def _create_scheme_profile_from_mongo(doc_index:int, headers_collection: pymongo.collection.Collection, isolate: str, scheme: str, scheme_loci: Dict[str, Any]) -> List[List[Union[str, int]]]:
        """
        return a list of allele designations for the given isolate and scheme, and optionally, the header corresponding to
        this profile (containing the locus name of the scheme)
        :param doc_index: document index if list of documents. If doc_index = 0 will also provide a header
        :param headers_collection: mongo opened headers collection
        :param isolate: str corresponding to the isolate name stored in _id from mongo isolates collection
        :param scheme: Typing scheme of interest
        :param scheme_loci: Dict containing scheme loci
        :return: list of allele found for this scheme in the given isolate + optionally the corresponding loci name
        """
        listofresultlists = []
        # This is the modified list of dicts to dict with list values created by
        # __convert_typinghitdictionaries_to_lists in mainmongo after the consulatancy session
        if doc_index == 0:
            header = ["isolate_id"]
            for locus in sorted(scheme_loci):
                header.append(locus)
            listofresultlists.append(header)
        hit_metadata_document = headers_collection.find_one({'type': 'hit_metadata'})
        allele_index = hit_metadata_document[f"{scheme}_loci"].index('Allele')
        identity_index = hit_metadata_document[f"{scheme}_loci"].index('% Identity')
        length_index = hit_metadata_document[f"{scheme}_loci"].index('HSP/Locus length')
        resultlist = [isolate]
        for locus in sorted(scheme_loci):
            allele_id = scheme_loci[locus][allele_index]
            if scheme_loci[locus][identity_index] == '100.00' and \
                    eval(scheme_loci[locus][length_index]) == 1.0:
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

    @staticmethod
    def _create_scheme_profile_from_json(doc_index: int, isolate: str, scheme_loci: List[str]) -> List[List[Union[str, int]]]:
        """
        return a list of allele designations for the given isolate and scheme, and optionally, the header corresponding to
        this profile (containing the locus name of the scheme)
        :param doc_index: document index
        :param isolate: str corresponding to the isolate name stored in _id from mongo isolates collection
        :param scheme_loci: Typing scheme of interest
        :return:  list of allele found for this scheme in the given isolate + optionally the corresponding loci name
        """
        listofresultlists = []
        # This is the original input provided by the pipeline
        if doc_index == 0:
            header = ["isolate_id"]
            for locus in scheme_loci:
                header.append(locus['Locus'])
            listofresultlists.append(header)
        resultlist = [isolate]
        for locus in scheme_loci:
            allele_id = locus['Allele']
            # what about possibility to write the eval to the mongodb document, this is not a possibility because then we lose the length information
            if locus['% Identity'] == '100.00' and eval(locus['HSP/Locus length']) == 1.0:
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

    @staticmethod
    def revert_typinghitlists_to_dictionaries(document: MongoRecordDict, headers_collection: pymongo.collection.Collection) -> None:
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
            return
        results_to_modify=document.get_json_results()
        #results_to_modify = (document['results'] if 'results' in document else document)  # this is not a deepcopy so results will be modified in document as well
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

    def get_any_results_version(self, isolate_id: str, searchkey: str, searchvalue: Union[str, int],
                                isolates_collection: pymongo.collection.Collection,
                                old_isolateresults_collection: pymongo.collection.Collection,
                                headers_collection: pymongo.collection.Collection) -> MongoRecordDict:
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
        current_version = MongoRecordDict(isolates_collection.with_options(read_concern=ReadConcern(level="majority")).find_one({'_id': isolate_id}))
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
                old_versions = list(map(lambda x: MongoRecordDict(x), old_isolateresults_collection.with_options(read_concern=ReadConcern(level="majority")).\
                    find({'isolates_id': isolate_id, searchkey: {'$gte': searchvalue}})))
                old_versions = sorted(old_versions, key=lambda x: convert_dmyhms_to_ymd(x['analysis_date']), reverse=True)
            else:  # key == 'analysis_date'
                old_versions = list(map(lambda x: MongoRecordDict(x), old_isolateresults_collection.with_options(read_concern=ReadConcern(level="majority")).\
                    find({'isolates_id': isolate_id})))
                # sort from most recent to oldest
                old_versions = sorted([x for x in old_versions if convert_dmyhms_to_ymd(x['analysis_date']) >= searchvalue], key=lambda x: convert_dmyhms_to_ymd(x['analysis_date']), reverse=True)
            if len(old_versions) > 0:
                old_versions_merged = old_versions[0]
                if len(old_versions) > 1:
                    for x in old_versions[1:]:
                        merge_mongo_dicts(old_versions_merged, x)
                merge_mongo_dicts(MongoRecordDict(current_version['results']), old_versions_merged)
            requested_document = current_version
        # 4. Revert the effective dict to list storage to a readable format for the html reporter
        self.revert_typinghitlists_to_dictionaries(requested_document, headers_collection)
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
