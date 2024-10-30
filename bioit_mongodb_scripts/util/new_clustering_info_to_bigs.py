import datetime
import logging
import socket
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSequences, TblProfiles, TblProfileFields, TblProfileMembers, \
    TblClassificationGroups, TblClassificationGroupProfiles, TblClassificationGroupProfileHistory, \
    TblClassificationSchemes, TblEavText, TblEavFields, TblMappingTable
from bioit_mongodb_scripts.config import CLUSTERING_CONFIG
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


class NewClusteringInfoToBigs:
    """
    Inserts all new clustering related info into BIGSdb, decides what is new based on a date that is stored
    in the update metadata collection. This date is updated at the successful end of this script.
    """
    def __init__(self, species: str, naive_clustering_distance_matrix_file: Path, cgmlst_bigsdb_scheme_id: int,
                 mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Intialises this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param naive_clustering_distance_matrix_file: The path to the naive clustering cgmlst distance matrix file
        :param cgmlst_bigsdb_scheme_id: The bigsdb SQL id of the cgMLST scheme
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :return: None
        """
        self._species = species
        self._cgmlst_bigsdb_scheme_id = cgmlst_bigsdb_scheme_id
        self._naive_clustering_distance_matrix_file = naive_clustering_distance_matrix_file

        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_AZURE')
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, \
            self._isolates_resequencing_collection = self._mongoinit.initialise_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = \
            self._mongoinit.initialise_clustering_collections()
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()
        self._hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        # Open sequences psql table connection
        self._seqdef_sequences_psql_tbl = TblSequences(self._species)
        # Prepare for main
        self._clustering_thresholds = CLUSTERING_CONFIG[f"clustering_thresholds_{self._species}"]
        self._new_temporary_alleles_update_date = self._get_temporary_alleles_update_date()
        self._last_date_of_update = self._get_last_date_of_update()
        if self._last_date_of_update is None:
            self._last_date_of_update = datetime.datetime(1970, 1, 1)  # unix time
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

    def _get_last_date_of_update(self) -> Optional[date]:
        """
        Retrieve in MongoDB the date of the last update.
        :return: a date in iso UTC format
        """
        query = self._update_metadata_collection.find_one({'metadata': 'last_update', 'host': socket.gethostname()})
        return query['last_update_date'] if query else None

    def _get_temporary_alleles_update_date(self) -> Optional[date]:
        """
        Retrieve the date 
        :return: a date in iso UTC format
        """
        query = self._update_metadata_collection.find_one({'metadata': 'last_update_temporary_alleles', 'host': socket.gethostname()})
        # this always needs to be found because the new temporary alleles runs before the new clustering info runs
        return query['last_update_date']
    
    def _get_new_st(self) -> List[Dict[str, Any]]:
        """
        Retrieve the new sequence types from the MongoDB sequence types collection which have been added since the
        date of the last update.
        :return: A list of documents containing the information about the new sequence types.
        """
        return list(self._st_collection.find({'insertion_date': {'$gt': self._last_date_of_update,
                                                                 '$lt': self._new_temporary_alleles_update_date}},
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
        Retrieve the cluster memberships that have been added or modified since the last date of update
        :return: A list of documents (dict) containing the information about the new cluster memberships.
        """
        return list(self._cluster_membership_collection.find({'insertion_date': {'$gt': self._last_date_of_update}}))

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
                                nullpresent = self._seqdef_sequences_psql_tbl.count_sequence_null((locus,))
                                if nullpresent[0][0] == 0:
                                    self._seqdef_sequences_psql_tbl.insert_sequence((locus, '0', 'null allele'))
                            seqdef_profilemembers_psql_tbl.insert_profile_member(('cgMLST', locus, st_id, allele_id))

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
        # get cgmlst_diff_fields
        with TblEavFields(self._species) as isolates_eavf_psql_tbl:
            cgmlst_diff_fields = isolates_eavf_psql_tbl.select_fields_cgmlstdifferences()

        # read distance matrix
        distance_matrix: np.array = np.load(str(self._naive_clustering_distance_matrix_file))

        # parse cgmlst distance thresholds from cgmlst_diff_fields
        for field in cgmlst_diff_fields:
            interval = field[0].split('_')[-1]
            interval_start = int(interval.split('-')[0])
            interval_stop = int(interval.split('-')[-1])
            # get all cgsts in mongodb:
            cgsts_per_isolate: List[Dict[str, Union[str, Dict[str, Optional[int]]]]] = \
                list(self._isolates_collection.find({}, {"results.cgST": 1, "_id": 1}))
            # check if field is possibly new by checking if there are any values for the field yet,
            # this feature is needed because fields can be added at different points in time and
            # would otherwise be skipped for isolates/cgsts already in the database
            with TblEavText(self._species) as isolates_eavt_psql_tbl:
                is_field_possibly_new = True if isolates_eavt_psql_tbl.select_count_eav_field((field[0],))[0][0] == 0 \
                                            else False
            if is_field_possibly_new:
                logging.info(f"Inserting cgMLST difference html fields for isolates present in Bigsdb")
                cgsts = set(x['results'].get('cgST') for x in cgsts_per_isolate)
                cgsts.discard(None)
                for cgst in cgsts:
                    self.___update_naive_clustering_implementation_for_one_cgst(
                        cgst, distance_matrix, interval_start, interval_stop, cgsts_per_isolate, field,
                        is_field_new=False)
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
                        indices = np.where((row_cgst >= interval_start) & (row_cgst <= interval_stop))[0]
                        if len(indices) > 0:
                            affected_and_new_cgsts.update(index + 1 for index in indices)

                    for cgst in affected_and_new_cgsts:
                        self.___update_naive_clustering_implementation_for_one_cgst(
                            cgst, distance_matrix, interval_start, interval_stop, cgsts_per_isolate, field,
                            is_field_new=False)

    def ___update_naive_clustering_implementation_for_one_cgst(
            self, cgst: int, distance_matrix: np.array, interval_start: int, interval_stop: int,
            cgsts_per_isolate: List[Dict[str, Union[str, Dict[str, Optional[int]]]]], field,
            is_field_new: bool = True) -> None:
        """
        Modularization function which updates the naive clustering in implementation in bigsdb for one specific cgST.
        :param cgst: cgST for which to update
        :param distance_matrix: cgST distance matrix
        :param interval_start: current cgMLST difference field's interval start
        :param interval_stop: current cgMLST difference field's interval stop
        :param cgsts_per_isolate: List of dictionaries extracted from MongoDB containing all pseudo_ids and their
        corresponding cgST
        :param field: the current cgMLST difference field
        :param is_field_new: Whether any value is already present for the current cgMLST difference field
        :return: None
        """
        with TblEavText(self._species) as isolates_eavt_psql_tbl, TblMappingTable(self._species) as \
                isolates_mapping_psql_tbl:
            # extract row
            row_cgst = distance_matrix[cgst - 1]
            # get all cgSTs within distance
            indices = np.where((row_cgst >= interval_start) & (row_cgst <= interval_stop))[0]
            if len(indices) > 0:
                if interval_start != 0:
                    # if interval_start != 0, then add the current cgST because it has not been picked up
                    # by the indices query, and it should be present itself (in practice up until now start is always 0)
                    indices = np.append(indices, cgst - 1)
                html = self.generate_htmlelement_cgstquery([x + 1 for x in indices],
                                                           self._cgmlst_bigsdb_scheme_id, field[0], self._species)
                for pseudo_id in [_dict['_id'] for _dict in cgsts_per_isolate
                                  if _dict['results'].get('cgST') == cgst]:
                    bigsdb_id_isolate = isolates_mapping_psql_tbl.select_isolate_id_for_pseudo_id((pseudo_id,))
                    # it is possible that new isolates have not been added to bigsdb yet with old cgSTs
                    if len(bigsdb_id_isolate) > 0:
                        if not is_field_new and isolates_eavt_psql_tbl.select_count_eav_id(
                                (str(bigsdb_id_isolate[0][0]), field[0]))[0][0] > 0:
                            isolates_eavt_psql_tbl.update_eav_id((html, str(bigsdb_id_isolate[0][0]),
                                                                  field[0]))
                            # it is also possible that the isolates in question do not have the fields
                            # yet because no cgST's were close up until now -> execute else
                            # Or since 2024/10/14 new cgST's also follow this route
                        else:
                            # For new fields and for affected isolates that did not have the field yet
                            isolates_eavt_psql_tbl.insert_eav_id((str(bigsdb_id_isolate[0][0]), field[0], html))

    @staticmethod
    def generate_htmlelement_cgstquery(cgsts: List[int], cgmlst_bigsdb_scheme_id: int,
                                       cgmlst_diff_field: str, species: str) -> str:
        """
        Generates a html element to be inserted into bigsdb that will query all isolates with certain
        cgSTs after clicking on it, also provides a preview of the number of those isolates using JavaScript
        and will provide a preview
        :param cgsts: the cgST's that should be included in the html query
        :param cgmlst_bigsdb_scheme_id: the scheme id of the cgMLST scheme in bigsdb (usually 2, after 1 mlst,
        but in the case of stec that has 2 mlst it is 3)
        :param cgmlst_diff_field: cgmlst difference field in bigsdb e.g. cgMLST_differences_1-10
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: html element that executes the javascript function replaceQueriedValue e.g.
        '<div id="cgMLST_differences_1-10"><script type="text/javascript">replaceQueriedValue(
        generateUrlCgst("mycobacterium", "2", ["1","2","3"]), "cgMLST_differences_1-10")</script>'
        """
        cgsts_plaintext = '","'.join(str(x) for x in cgsts)
        url = f'generateUrlCgst("{species}", "{cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
        html_element = f'<div id="{cgmlst_diff_field}"><script type="text/javascript">replaceQueriedValue({url}, ' \
                       f'"{cgmlst_diff_field}")</script>'
        return html_element

    def __update_last_update_date(self) -> None:
        """
        Update into Mongodb the last date of update once the update has been carried out.
        :return: None.
        """
        self._update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {'metadata': 'last_update', 'host': socket.gethostname()},
            {"$set": {'last_update_date': self._new_temporary_alleles_update_date}}, upsert=True)

    def __del__(self) -> None:
        """
        Closes the isolates psql table when the class is closed
        :return: None
        """
        self._seqdef_sequences_psql_tbl.close()
