import datetime
import logging
import socket
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSequences, TblProfiles, TblProfileFields, TblProfileMembers, \
    TblClassificationGroups, TblClassificationGroupProfiles, TblClassificationGroupProfileHistory, \
    TblClassificationSchemes
from bioit_mongodb_scripts.config import CLUSTERING_CONFIG
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


class NewClusteringInfoToBigs:
    def __init__(self, species: str, mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Intialises this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :return None
        """
        self._species = species
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()
        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data)
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = self._mongoinit.\
            initialise_clustering_collections()
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()
        self._hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        # Open sequences psql table connection
        self._seqdef_sequences_psql_tbl = TblSequences(self._species)
        # Prepare for main
        self._clustering_thresholds = CLUSTERING_CONFIG[f"clustering_thresholds_{self._species}"]
        self._current_update_date = datetime.datetime.utcnow()
        self._last_date_of_update = self._get_last_date_of_update()
        if self._last_date_of_update is None:
            self._last_date_of_update = datetime.datetime(1970, 1, 1)  # unix time
            self._update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).\
                insert_one({'metadata': 'last_update', 'last_update_date': self._last_date_of_update})
        self._new_sequences = self._get_new_sequence()
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
        Runs the upload of new alleles and clustering from mongo to bigs.
        :return: None.
        """
        if len(self._new_sequences) > 0:
            self.__insert_new_alleles()
        if len(self._new_st) > 0:
            self.__insert_sequence_types()
        if len(self._new_cluster_membership) > 0:
            self.__insert_or_update_clustering()
        self.__update_last_update_date()

    def _get_last_date_of_update(self) -> Optional[date]:
        """
        Retrieve in mongo db the date of the last update.
        :return: a date in iso UTC format
        """
        query = self._update_metadata_collection.find_one({'metadata': 'last_update'})
        return query['last_update_date'] if query else None

    def _get_new_sequence(self) -> List[Dict[str, Any]]:
        """
        Retrieve all the new hashed alleles from the mongo hashed alleles collection that have been added since the
        date of the last update.
        :return: A list of documents containing the information about the new alleles.
        """
        return list(self._hashed_ad_collection.find({'insertion_date': {'$gt': self._last_date_of_update},
                                                     'resolved_AD': 0}))

    def _get_new_st(self) -> List[Dict[str, Any]]:
        """
        Retrieve the new sequence types from the mongo db sequence types collection which have been added since the
        date of the last update.
        :return: A list of documents containing the information about the new sequence types.
        """
        return list(self._st_collection.find({'insertion_date': {'$gt': self._last_date_of_update}}))

    def _get_st_headers(self) -> Dict[str, Any]:
        """
        Retrieve the sequence types headers from the sequence type collection from Mongo DB
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

    def __insert_new_alleles(self) -> None:
        """
        Insert into BIGSdb the new alleles retrieved during the initialization.
        :return: None.
        """
        ordered_by_locus_dict = self.___order_sequences_by_locus()
        for locus in ordered_by_locus_dict:
            # fetch all alleles ids already in bigs
            set_alleleid = set(item[0] for item in self._seqdef_sequences_psql_tbl.select_allele_from_locus((locus,)))
            for new_allele in ordered_by_locus_dict[locus]:
                if new_allele['temp_allele_name'] not in set_alleleid:
                    self._seqdef_sequences_psql_tbl.insert_sequence((locus, new_allele['temp_allele_name'],
                                                                     new_allele['allele_sequence']))
                    logging.info(f"id {new_allele['temp_allele_name']} inserted into locus {locus}")

    def ___order_sequences_by_locus(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Order the sequences by locus in order to be able to add the alleles by locus in an easy way.
        :return: dictionary of loci and a list of their corresponding hashed dictionaries
        """
        order_seqs = {}
        for seq in self._new_sequences:
            key = seq['locus']
            if key in order_seqs:
                order_seqs[key].append(seq)
            else:
                order_seqs[key] = [seq]
        return order_seqs

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
                        logging.info(f"start insert of {st['cgST']}")
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
        with TblClassificationGroups(self._species) as seqdef_clgr_psql_tbl, \
            TblClassificationGroupProfiles(self._species) as seqdef_clgrpr_psql_tbl, \
                TblClassificationGroupProfileHistory(self._species) as seqdef_clgrprhist_psql_tbl:
            for cl_membership in self._new_cluster_membership:
                cg_scheme_id = self._clustering_thresholds.index(cl_membership['threshold']) + 1
                profile_id = cl_membership['cgST']
                group_id = cl_membership['clustering_membership']
                seqdef_clgr_psql_tbl.count_group((cg_scheme_id, group_id))
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

    def __update_last_update_date(self) -> None:
        """
        Update into Mongodb the last date of update once the update has been carried out.
        :return: None.
        """
        self._update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {'metadata': 'last_update'}, {
                "$set": {'last_update_date': self._current_update_date}})

    def __exit__(self) -> None:
        """
        Closes the isolates psql table when the class is closed
        :return: None
        """
        self._seqdef_sequences_psql_tbl.close()
