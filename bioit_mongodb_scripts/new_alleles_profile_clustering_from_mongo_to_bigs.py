import datetime
import logging
import os
import smtplib
import socket
import sys
import traceback
from datetime import date
from email.message import EmailMessage
from typing import Any, Dict, List, Tuple
from pathlib import Path

import pymongo
import yaml
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSequences, TblProfiles, TblProfileFields, TblProfileMembers, TblClassificationGroups, TblClassificationGroupProfiles, TblClassificationGroupProfileHistory, TblClassificationSchemes
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.config import MONGO_CONFIG
from bioit_mongodb_scripts.config import CLUSTERING_CONFIG

def _send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)
    logging.info(content)

class NewAllelesProfileClusteringFromMongoToBigs:
    def __init__(self, species: str, st_collection: pymongo.collection.Collection, hashed_ad_collection: pymongo.collection.Collection,
                 cluster_membership_collection: pymongo.collection.Collection, update_metadata_collection: pymongo.collection.Collection,
                 headers_collection: pymongo.collection.Collection) -> None:
        """
        Initialization of the class.
        :param species: the species that needs to be updated
        :param st_collection: the sequence type collection from the mongo db of the species
        :param hashed_ad_collection: the ashed allele collection of mongo db of the species
        :param cluster_membership_collection: cluster membership collection from the mongo db of the species
        :param update_metadata_collection: the update metadata collection from the mongo db of the species
        :param headers_collection: collection containing headers for typing locus dictionaries + headers of cgmlst profiles
        """
        self._species = species
        self.st_collection = st_collection
        self.headers_collection = headers_collection
        self.hashed_ad_collection = hashed_ad_collection
        self.cluster_membership_collection = cluster_membership_collection
        self.update_metadata_collection = update_metadata_collection
        self._seqdef_sequences_psql_tbl = TblSequences(self._species)
        self.clustering_thresholds = CLUSTERING_CONFIG[f"clustering_thresholds_{self._species}"]
        self.current_update_date = datetime.datetime.utcnow()
        self.last_date_of_update = self._get_last_date_of_update()
        if self.last_date_of_update == None:
            self.last_date_of_update = datetime.datetime(1970, 1, 1)  # unix time
            self.update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
            {'metadata': 'last_update',
            'last_update_date': datetime.datetime(1970, 1, 1)})
        self.new_sequences = self._get_new_sequence()
        self.new_st = self._get_new_st()
        self.st_headers = self._get_st_headers()
        self.new_cluster_membership = self._get_new_cluster_membership()

    def _get_last_date_of_update(self) -> date:
        """
        Retrieve in mongo db the date of the last update.
        :return: a date in iso UTC format
        """
        query = self.update_metadata_collection.find_one({'metadata': 'last_update'})
        if query:
            return query['last_update_date']
        else:
            return query

    def _get_new_sequence(self) -> list:
        """
        Retrieve all the new hashed alleles from the mongo hashed alleles collection that have been added since the
        date of the last update.
        :return: A list of documents containing the information about the new alleles.
        """
        query_seq = self.hashed_ad_collection.find({'insertion_date': {'$gt': self.last_date_of_update}})
        results = list(query_seq)
        return results

    def _get_new_st(self) -> list:
        """
        Retrieve the new sequence types from the mongo db sequence types collection which have been added since the
        date of the last update.
        :return: A list of documents containing the information about the new alleles.
        """
        query_st = self.st_collection.find({'insertion_date': {'$gt': self.last_date_of_update}})
        sts = list(query_st)
        return sts

    def _get_st_headers(self) -> Dict[str, str]:
        """
        Retrieve the sequence types headers from the sequence type collection from Mongo DB
        :return: The document (dict) containing the headers.
        """
        return self.headers_collection.find_one({'type': 'cgmlst_headers'})

    def _get_new_cluster_membership(self) -> list:
        """
        Retrieve the cluster memberships that have been added or modified since the last date of update
        :return: A list of documents (dict) containing the information about the new cluster memberships.
        """
        query_cluster = self.cluster_membership_collection.find({'insertion_date': {'$gt': self.last_date_of_update}})
        cluster = list(query_cluster)
        return cluster

    def insert_into_bigs(self) -> None:
        """
        Main method to initiate the insertion into BIGSdb of the new results retrieved during the initialization.
        :return: None.
        """
        if len(self.new_sequences) > 0:
            self._insert_new_alleles()
        if len(self.new_st) > 0:
            self._insert_sequence_types()
        if len(self.new_cluster_membership) > 0:
            self._insert_or_update_clustering()
        self._update_last_update_date()

    def _insert_new_alleles(self) -> None:
        """
        Insert into BIGSdb the new alleles retrieved during the initialization.
        :return: None.
        """
        ordered_by_scheme_dict = self._order_sequences_by_locus()
        for scheme_loci in ordered_by_scheme_dict:
            scheme, locus = scheme_loci.split(',')
            # fetch all alleles ids already in bigs
            listoftuples = self._seqdef_sequences_psql_tbl.select_allele_from_locus((locus,))
            list_alleleid: List[str] = [x[0] for x in listoftuples]
            for new_allele in ordered_by_scheme_dict[scheme_loci]:
                if new_allele['temp_allele_name'] not in list_alleleid:
                    self._seqdef_sequences_psql_tbl.insert_sequence((locus, new_allele['temp_allele_name'], new_allele['allele_sequence']))
                    logging.info(f"id {new_allele['temp_allele_name']} inserted into locus {locus}")

    def _order_sequences_by_locus(self) -> Dict[str, Any]:
        """
        Order the sequences by locus in order to be able to add the alleles by locus in an easy way.
        :return: None
        """
        order_seqs = {}
        for seq in self.new_sequences:
            key = f"{seq['scheme']},{seq['locus']}"
            if key in order_seqs:
                order_seqs[key].append(seq)
            else:
                order_seqs[key] = [seq]
        return order_seqs

    def _insert_sequence_types(self) -> None:
        """
        Insert the new sequence types retrieved during the initialization into BIGSdb.
        :return: None.
        """
        with TblProfiles(self._species) as seqdef_profiles_psql_tbl:
            listoftuples: List[Tuple[int]] = seqdef_profiles_psql_tbl.select_profile(('cgMLST',))
            primary_fields = [int(x[0]) for x in listoftuples] if listoftuples is not None else []
            with TblProfileMembers(self._species) as seqdef_profilemembers_psql_tbl, \
                    TblProfileFields(self._species) as seqdef_profilefields_psql_table:
                for st in self.new_st:
                    if int(st['cgST']) not in primary_fields:
                        logging.info(f"start insert of {st['cgST']}")
                        st_id = st['cgST']
                        # insertion of the st id into the profiles table
                        seqdef_profiles_psql_tbl.insert_profile(('cgMLST', st_id))
                        # insertion of the st in the profiles_fields
                        seqdef_profilefields_psql_table.insert_profile_field(('cgMLST', 'cgST', st_id, st_id))
                        alleles = st['cgMLST']
                        for locus, allele_id in zip(self.st_headers['headers'], alleles):
                            if str(allele_id) == '0':  # this will create a ForeignKeyViolation error so we prevent this
                                # by inserting a null allele if not yet present
                                nullpresent = self._seqdef_sequences_psql_tbl.count_sequence_null((locus,))
                                if nullpresent[0][0] == 0:
                                    self._seqdef_sequences_psql_tbl.insert_sequence((locus, '0', 'null allele'))
                            seqdef_profilemembers_psql_tbl.insert_profile_member(('cgMLST', locus, st_id, allele_id))

    def _insert_or_update_clustering(self) -> None:
        """
        Insert or update new cluster memberships retrieved during the initialization into BIGSdb. In addition, if a
        cluster is merged, the cluster membership modification is also recorded into BIGSdb
        (classification_group_profile_history table).
        :return: None.
        """
        groups_merged = set()
        self.__check_for_classification_schemes()
        with TblClassificationGroups(self._species) as seqdef_clgr_psql_tbl, \
            TblClassificationGroupProfiles(self._species) as seqdef_clgrpr_psql_tbl, \
            TblClassificationGroupProfileHistory(self._species) as seqdef_clgrprhist_psql_tbl:
            for cl_membership in self.new_cluster_membership:
                cg_scheme_id = self.clustering_thresholds.index(cl_membership['threshold']) + 1
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
                        seqdef_clgrprhist_psql_tbl.insert_history(('cgMLST', profile_id, cg_scheme_id, str(current_bigsdb_group[0][0])))
                        if current_bigsdb_group[0][0] not in groups_merged:
                            logging.debug(f'group {current_bigsdb_group[0][0]} is merged into {group_id}')
                            groups_merged.add(current_bigsdb_group[0][0])
                            # update group table
                            seqdef_clgr_psql_tbl.inactivate_group((profile_id, str(current_bigsdb_group[0][0])))

    def __check_for_classification_schemes(self) -> None:
        """
        Check if the classification schemes are already into BIGSdb. if not, insert them.
        :return:
        """
        with TblClassificationSchemes(self._species, 'seqdef') as seqdef_clsch_psql_tbl, \
            TblClassificationSchemes(self._species, 'isolates') as isolates_clsch_psql_tbl:
            query_res = seqdef_clsch_psql_tbl.select_cgschemes()
            if len(query_res) > 0:
                thresholds_presents = [x[1] for x in query_res]
                idx_max = max([int(x[0]) for x in query_res])
            else:
                thresholds_presents = []
                idx_max = 0
            for threshold in self.clustering_thresholds:
                if threshold not in thresholds_presents:
                    name = f"cgMLST_{threshold}_diffs_clustering"
                    description = f"cgMLST profiles clustering at the threshold of {threshold} allelic differences"
                    # initialize in seqdef
                    seqdef_clsch_psql_tbl.insert_cgscheme_seqdef((str(idx_max + 1), 'cgMLST', name, description, threshold, str(idx_max + 1)))
                    isolates_clsch_psql_tbl.insert_cgscheme_isolates((str(idx_max + 1), 'cgMLST', name, description, threshold, str(idx_max + 1), str(idx_max + 1)))
                    idx_max += 1
                else:
                    logging.debug(f"Threshold {threshold} already present")

    def _update_last_update_date(self) -> None:
        """
        Update into Mongodb the last date of update once the update has been carried out.
        :return: None.
        """
        self.update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {'metadata': 'last_update'}, {
                "$set": {'last_update_date': self.current_update_date}})

    def __exit__(self) -> None:
        """
        Closes the isolates psql table when the class is closed
        :return: None
        """
        self._seqdef_sequences_psql_tbl.close()


def run_upload_new_alleles_profiles_clustering_from_mongo_to_bigs(species: str) -> None:
    """
    Runs the uplaod of new alleles and clustering from mongo to bigs
    :param species: the species to which the database needs to be uploaded
    :return: None
    """
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    # Open collections
    mongoinit = MongoInitialisation(species)
    hashed_ad_collection = mongoinit.initialise_hashing_collection()
    st_collection, cluster_membership_collection, cluster_merging_collection = \
        mongoinit.initialise_clustering_collections()
    update_collection = mongoinit.initialise_update_collection()
    headers_collection = mongoinit.initialise_headers_collection()

    # initialize the class
    try:
        updater = NewAllelesProfileClusteringFromMongoToBigs(species, st_collection, hashed_ad_collection,
                                        cluster_membership_collection, update_collection, headers_collection)
        updater.insert_into_bigs()
    except Exception as exceptionmessage:
        _send_email(f"{Path(__file__).name} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")
