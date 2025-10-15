import logging
import socket
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from psycopg.types.json import Jsonb
from pymongo.write_concern import WriteConcern

from bioit_mongodb_scripts.util.mongo_clustering_config_provider import MongoClusteringConfigProvider

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblAnalysisResults, TblSequences, TblProfiles, TblProfileFields, TblProfileMembers, \
    TblClassificationGroups, TblClassificationGroupProfiles, TblClassificationGroupProfileHistory, \
    TblClassificationSchemes, TblMappingTable
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import send_email


class NewClusteringInfoToBigs:
    """
    Inserts all new clustering related info into BIGSdb, decides what is new based on a date that is stored
    in the update metadata collection. This date is updated at the successful end of this script.
    """

    def __init__(self, species: str, naive_clustering_distance_matrix_file: Path, cgmlst_bigsdb_scheme_id: int,
                 mongo_config_provider: MongoConfigProvider) -> None:
        """
        Initialises this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param naive_clustering_distance_matrix_file: The path to the naive clustering cgmlst distance matrix file
        :param cgmlst_bigsdb_scheme_id: The bigsdb SQL id of the cgMLST scheme
        :param mongo_config_provider: the mongodb configuration provider
        :return: None
        """
        self._species = species
        self._cgmlst_bigsdb_scheme_id = cgmlst_bigsdb_scheme_id
        self._naive_clustering_distance_matrix_file = naive_clustering_distance_matrix_file

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_provider.get_azure_connection_string(self._species), mongo_config_provider.dtap)
        self._isolates_collection, _, _, _, _ = self._mongoinit.initialise_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = \
            self._mongoinit.initialise_clustering_collections()
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()
        # Prepare for main
        clustering_config_provider = MongoClusteringConfigProvider(self._species)
        lowest_threshold = clustering_config_provider.get_lowest_clustering_threshold()
        highest_threshold = clustering_config_provider.get_highest_clustering_threshold()
        self._clustering_thresholds = clustering_config_provider.get_clustering_thresholds()
        self._results_dict: dict[int, list[dict[str, str]]] = {lowest_threshold: [], highest_threshold: []}
        self._new_temporary_alleles_update_date = self._get_temporary_alleles_update_date()
        self._new_st = self._get_new_st()
        self._st_headers = self._get_st_headers()
        self._new_cluster_membership = self._get_new_cluster_membership()

        # Execute main function
        try:
            self._insert_into_bigs()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: "
                            f"{exceptionmessage}\n{traceback.format_exc()}")

    def _insert_into_bigs(self) -> None:
        """
        Main method to initiate the insertion into BIGSdb of the new results retrieved during the initialization.
        Inserts cgST's and clustering info from MongoDB to BIGSdb.
        :return: None.
        """
        if len(self._new_st) > 0:
            self.__insert_sequence_types()
        if len(self._new_cluster_membership) > 0:
            self.__insert_or_update_clustering()
        self.__update_naive_clustering_implementation()
        self.__update_last_update_date()

    def _get_temporary_alleles_update_date(self) -> Optional[date]:
        """
        Retrieve the last date that the last temporary alleles were inserted to use this as a maximum date for the new
        cgST insertion.
        :return: a date in iso UTC format
        """
        query = self._update_metadata_collection.find_one(
            {'metadata': 'last_update_temporary_alleles', 'host': socket.gethostname()})
        # this always needs to be found because the new temporary alleles runs before the new clustering info runs
        return query['last_update_date']

    def _get_new_st(self) -> List[Dict[str, Any]]:
        """
        Retrieve the new sequence types from the MongoDB sequence types collection which have been added since the
        last update of clustering.
        :return: A list of documents containing the information about the new sequence types.
        """
        return list(
            self._st_collection.find({'$and': [{'bigsdb_status': 'pending'}, {'select_for_bigsdb_insertion': True}]},
                                     sort=[('cgST', 1)]))

    def _get_st_headers(self) -> Dict[str, Any]:
        """
        Retrieve the sequence types headers from the sequence type collection from MongoDB
        :return: The document (dict) containing the allele names as a list under the 'headers' key.
        This allele names header corresponds to the list of alleles in the profiles in the sequence_types collection.
        """
        return self._headers_collection.find_one({'type': 'cgmlst_headers'})

    def _get_new_cluster_membership(self) -> List[Dict[str, Any]]:
        """
        Retrieve the cluster memberships that have been added or modified between the last clustering update and last
        update of temporary alleles
        :return: A list of documents (dict) containing the information about the new cluster memberships.
        """
        return list(self._cluster_membership_collection.find(
            {'$and': [{'cluster_updated': True}, {'select_for_bigsdb_insertion': True}]}))

    def __insert_sequence_types(self) -> None:
        """
        Insert the new sequence types retrieved during the initialization into BIGSdb.
        :return: None.
        """
        with TblProfiles(self._species) as seqdef_profiles_psql_tbl:
            listoftuples: List[Tuple[int]] = seqdef_profiles_psql_tbl.select_profile(('cgMLST',))
            primary_fields = [int(x[0]) for x in listoftuples] if listoftuples else []
            with TblProfileMembers(self._species) as seqdef_profilemembers_psql_tbl, \
                    TblProfileFields(self._species) as seqdef_profilefields_psql_table:
                for st in self._new_st:
                    if int(st['cgST']) not in primary_fields:
                        logging.info(f"Inserting cgST {st['cgST']} ...")
                        st_id = st['cgST']
                        # insertion of the st id into the profiles table
                        seqdef_profiles_psql_tbl.insert_profile(('cgMLST', st_id))
                        # insertion of the st in the profiles_fields
                        seqdef_profilefields_psql_table.insert_profile_field(('cgMLST', 'cgST', st_id, st_id))
                        alleles = st['cgMLST']
                        for locus, allele_id in zip(self._st_headers['headers'], alleles):
                            if str(allele_id) == '0':  # this will create a ForeignKeyViolation error so we prevent this
                                # by inserting a null allele if not yet present
                                with TblSequences(self._species) as seqdef_sequences_psql_tbl:
                                    nullpresent = seqdef_sequences_psql_tbl.count_sequence_null((locus,))
                                    if nullpresent[0][0] == 0:
                                        seqdef_sequences_psql_tbl.insert_sequence((locus, '0', 'null allele'))
                            seqdef_profilemembers_psql_tbl.insert_profile_member(('cgMLST', locus, st_id, allele_id))
                        self._st_collection.update_one({'cgST': st_id},
                                                       {'$set': {'bigsdb_status': 'inserted',
                                                                 'select_for_bigsdb_insertion': False}})

    def __insert_or_update_clustering(self) -> None:
        """
        Insert or update new cluster memberships retrieved during the initialization into BIGSdb. In addition, if a
        cluster is merged, the cluster membership modification is also recorded into BIGSdb
        (classification_group_profile_history table).
        :return: None.
        """
        groups_merged = set()
        self.___check_for_classification_schemes()
        threshold_bigsdbcgschemeid_dict = {}
        with TblClassificationSchemes(self._species, 'isolates') as isolates_clsch_psql_tbl:
            for threshold in self._clustering_thresholds:
                threshold_bigsdbcgschemeid_dict[threshold] = \
                    str(isolates_clsch_psql_tbl.select_cgschemeid_by_threshold(
                        (threshold,))[0][0])
        with TblClassificationGroups(self._species) as seqdef_clgr_psql_tbl, \
                TblClassificationGroupProfiles(self._species) as seqdef_clgrpr_psql_tbl, \
                TblClassificationGroupProfileHistory(self._species) as seqdef_clgrprhist_psql_tbl:
            for cl_membership in self._new_cluster_membership:
                cg_scheme_id = threshold_bigsdbcgschemeid_dict[int(cl_membership['threshold'])]
                profile_id = cl_membership['cgST']
                group_id = cl_membership['clustering_membership']
                query_group_exists = seqdef_clgr_psql_tbl.count_group((cg_scheme_id, group_id))
                if query_group_exists[0][0] == 0:
                    seqdef_clgr_psql_tbl.insert_group((cg_scheme_id, group_id))
                    seqdef_clgrpr_psql_tbl.insert_profile((cg_scheme_id, group_id, profile_id, 'cgMLST'))
                else:
                    # group exists so now need to check if clustering membership already present
                    current_bigsdb_group = seqdef_clgrpr_psql_tbl.select_profile_group((cg_scheme_id, str(profile_id)))
                    if not current_bigsdb_group:
                        seqdef_clgrpr_psql_tbl.insert_profile((cg_scheme_id, group_id, profile_id, 'cgMLST'))
                    elif int(current_bigsdb_group[0][0]) != int(group_id):
                        seqdef_clgrpr_psql_tbl.update_profile_group((group_id, cg_scheme_id, profile_id))
                        seqdef_clgrprhist_psql_tbl.insert_history(('cgMLST', profile_id, cg_scheme_id,
                                                                   str(current_bigsdb_group[0][0])))
                        if current_bigsdb_group[0][0] not in groups_merged:
                            logging.debug(f'group {current_bigsdb_group[0][0]} is merged into {group_id}')
                            groups_merged.add(current_bigsdb_group[0][0])
                            # update group table
                            seqdef_clgr_psql_tbl.inactivate_group((profile_id, str(current_bigsdb_group[0][0])))
                update_fields = {'$set': {'cluster_updated': False, 'select_for_bigsdb_insertion': False}}
                self._cluster_membership_collection.update_one({'_id': cl_membership['_id']}, update_fields)

    def ___check_for_classification_schemes(self) -> None:
        """
        Check if the classification schemes are already into BIGSdb. if not, insert them.
        :return: None
        """
        with TblClassificationSchemes(self._species, 'seqdef') as seqdef_clsch_psql_tbl, \
                TblClassificationSchemes(self._species, 'isolates') as isolates_clsch_psql_tbl:
            query_res = seqdef_clsch_psql_tbl.select_cgschemes()
            if len(query_res) > 0:
                thresholds_presents = set(x[1] for x in query_res)
                idx_max = max([int(x[0]) for x in query_res])
            else:
                thresholds_presents = set()
                idx_max = 0
            for threshold in self._clustering_thresholds:
                if threshold not in thresholds_presents:
                    name = f"cgMLST_{threshold}_diffs_clustering"
                    description = f"cgMLST profiles clustering at the threshold of {threshold} allelic differences"
                    # initialize in seqdef
                    seqdef_clsch_psql_tbl.insert_cgscheme_seqdef((str(idx_max + 1), 'cgMLST', name, description,
                                                                  threshold, str(idx_max + 1)))
                    isolates_clsch_psql_tbl.insert_cgscheme_isolates((str(idx_max + 1), 'cgMLST', name, description,
                                                                      threshold, str(idx_max + 1), str(idx_max + 1)))
                    idx_max += 1
                else:
                    logging.debug(f"Threshold {threshold} already present")

    def __update_naive_clustering_implementation(self) -> None:
        """
        Reads the distance matrix, and inserts/updates the corresponding naive clustering fields in bigsdb
        :return: None
        """

        # read distance matrix
        distance_matrix: np.ndarray = np.load(str(self._naive_clustering_distance_matrix_file))
        # parse cgmlst distance thresholds
        for threshold in self._clustering_thresholds:
            max_allelic_distance = threshold
            assay_name = f'cgST_with_max_{max_allelic_distance}_allelic_dist'

            # get all cgsts in mongodb:
            cgsts_per_isolate: List[Dict[str, Union[str, Dict[str, Optional[int]]]]] = \
                list(self._isolates_collection.find({}, {"results.cgST": 1, "_id": 1}))
            # check if field is possibly new by checking if there are any values for the field yet,
            # this feature is needed because fields can be added at different points in time and
            # would otherwise be skipped for isolates/cgsts already in the database
            with TblAnalysisResults(self._species) as isolates_ana_res_psql_tbl:
                assay_already_in_db = isolates_ana_res_psql_tbl.is_field_already_present_in_postgres((assay_name,))[0][0]
            if not assay_already_in_db:
                logging.info(f"Inserting cgMLST clustering html links in analysis table for all isolates present in Bigsdb")
                cgsts = set(x['results'].get('cgST') for x in cgsts_per_isolate)
                cgsts.discard(None)
                for cgst in cgsts:
                    self.__update_naive_clustering_values_for_one_cgst(
                        cgst, distance_matrix, max_allelic_distance, cgsts_per_isolate, assay_name)
            else:
                if len(self._new_st) > 0:
                    cgsts = [x['cgST'] for x in self._new_st]
                    # older cgsts might be affected by multiple newer ones;
                    # therefore a set is used to combine them to be able to loop over after
                    affected_and_new_cgsts = set()
                    for cgst in cgsts:
                        # extract row
                        row_cgst = distance_matrix[cgst - 1]
                        # get all cgSTs within distance
                        indices = np.where(row_cgst <= max_allelic_distance)[0]
                        cgst_in_this_cluster = [x + 1 for x in indices]
                        if len(cgst_in_this_cluster) > 0:
                            affected_and_new_cgsts.update(cgst_in_this_cluster)

                    for cgst in affected_and_new_cgsts:
                        self.__update_naive_clustering_values_for_one_cgst(
                            cgst, distance_matrix, max_allelic_distance, cgsts_per_isolate, assay_name)
        self.__insert_cgst_cluster_link_in_analysis_table(self._results_dict)

    def __update_naive_clustering_values_for_one_cgst(
            self, cgst: int, distance_matrix: np.ndarray, max_allelic_distance: int,
            cgsts_per_isolate: List[Dict[str, Union[str, Dict[str, Optional[int]]]]], assay_name: str) -> None:
        """
        Modularization function which updates the naive clustering in implementation in bigsdb for one specific cgST.
        :param cgst: cgST for which to update
        :param distance_matrix: cgST distance matrix
        :param max_allelic_distance: current cgMLST difference field's interval stop
        :param cgsts_per_isolate: List of dictionaries extracted from MongoDB containing all pseudo_ids and their corresponding cgST
        :param assay_name: name used to refer to the current criteria used to cluster the cgSTs (e.g. cgST_with_max_4_allelic_dist)
        :return: None
        """
        with TblMappingTable(self._species) as isolates_mapping_psql_tbl:
            # extract row for current cgst
            row_cgst = distance_matrix[cgst - 1]
            # get all cgSTs with allelic distance <= max_allelic_distance to current cgst
            indices_of_cgst_to_cluster = np.where(row_cgst <= max_allelic_distance)[0]
            cgst_in_this_cluster = [x + 1 for x in indices_of_cgst_to_cluster]
            if len(cgst_in_this_cluster) > 0:
                html_javascript_link = self.generate_html_js_cgstquery(cgst_in_this_cluster, self._cgmlst_bigsdb_scheme_id, assay_name, self._species)
                pseudo_ids_from_this_cluster = [_dict['_id'] for _dict in cgsts_per_isolate if _dict['results'].get('cgST') == cgst]
                for pseudo_id in pseudo_ids_from_this_cluster:
                    isolate_id = isolates_mapping_psql_tbl.select_isolate_id_for_pseudo_id((pseudo_id,))
                    # it is possible that new isolates have not been added to bigsdb yet with old cgSTs
                    if isolate_id:
                        self._results_dict[max_allelic_distance].append({isolate_id: html_javascript_link})

    def __insert_cgst_cluster_link_in_analysis_table(self, results_dict_filled_in: dict[int, list[dict[str, str]]]) -> None:
        """
        Use the results dict filled in during the naive clustering update to insert the html links in the analysis_results table of BIGsdb
        :param results_dict_filled_in: dict containing the results to insert into bigsdb
        :return: None
        """
        results_dict_ordered = self.__convert_results_dict(results_dict_filled_in)
        with TblAnalysisResults(self._species) as isolates_ana_res_psql_tbl:
            for isolate_id, results in results_dict_ordered.items():
                json_layout = {}
                for item in results:
                    json_layout.update(item)
                value_already_found_in_postgres = isolates_ana_res_psql_tbl.is_field_already_set_for_this_isolate(('cgST_clustering_on_allelic_dist', isolate_id))[0][0]
                if value_already_found_in_postgres:
                    isolates_ana_res_psql_tbl.update_analysis_results_isolate_id((Jsonb(json_layout), isolate_id, 'cgST_clustering_on_allelic_dist'))
                else:
                    # For new fields and for affected isolates that did not have the field yet
                    isolates_ana_res_psql_tbl.insert_analysis_results_isolate_id(('cgST_clustering_on_allelic_dist', isolate_id, Jsonb(json_layout)))

    @staticmethod
    def __convert_results_dict(dict_to_convert: dict[int, list[dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
        """
        Converts a dict of the form:
        {'thresholdA': [{id_1: valA1}, {id_2: valA2}], 'thresholdB': [{id_1: valB1}, {id_2: valB2}]}
        into:
        {'id_1': [{'thresholdA': valA1}, {'thresholdB': valB1}], 'id_2': [{'thresholdA': valA2}, {'thresholdB': valB2}]}
        :return: dict with the converted structure
        """
        output = {}
        for threshold, list_of_results in dict_to_convert.items():
            for item in list_of_results:
                for isolate_id, html_js_link in item.items():
                    output.setdefault(isolate_id, []).append({threshold: html_js_link})
        return output

    @staticmethod
    def generate_html_js_cgstquery(cgsts: List[int], cgmlst_bigsdb_scheme_id: int, assay_name: str, species: str) -> str:
        """
        Generates the html element containing the javascript function to query the cgST's clustered together in BIGSdb interface
        :param cgsts: the cgST's that should be included in the html query
        :param cgmlst_bigsdb_scheme_id: the scheme id of the cgMLST scheme in bigsdb (usually 2, after 1 mlst)
        :param assay_name: name used to refer to the current criteria used to cluster the cgSTs (e.g. cgST_with_max_4_allelic_dist)
        :param species: commonly used bioit species name
        :return: html element containing the javascript function used in bigsdb
        """
        cgsts_plaintext = '","'.join(str(x) for x in cgsts)
        url = f'generateUrlCgst("{species}", "{cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
        html_element = f'<div id="{assay_name}"><script type="text/javascript">replaceQueriedValue({url}, ' \
                       f'"{assay_name}")</script>'
        return html_element

    def __update_last_update_date(self) -> None:
        """
        Update into Mongodb the last date of update once the update has been carried out.
        :return: None.
        """
        self._update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {'metadata': 'last_update', 'host': socket.gethostname()},
            {"$set": {'last_update_date': self._new_temporary_alleles_update_date}}, upsert=True)
