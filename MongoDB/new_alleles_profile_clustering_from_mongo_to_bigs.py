import datetime
import logging
import os
import smtplib
import socket
import sys
import traceback
from datetime import date
from email.message import EmailMessage
from typing import Dict

import pymongo
import yaml
from pymongo.write_concern import WriteConcern

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from MongoDB.util.mongo_initialisation import MongoInitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.config import CLUSTERING_CONFIG

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
                 cluster_membership_collection: pymongo.collection.Collection, update_metadata_collection: pymongo.collection.Collection) -> None:
        """
        Initialization of the class.
        :param species: the species that needs to be updated
        :param st_collection: the sequence type collection from the mongo db of the species
        :param hashed_ad_collection: the ashed allele collection of mongo db of the species
        :param cluster_membership_collection: cluster membership collection from the mongo db of the species
        :param update_metadata_collection: the update metadata collection from the mongo db of the species
        """
        self.species = species
        self.st_collection = st_collection
        self.hashed_ad_collection = hashed_ad_collection
        self.cluster_membership_collection = cluster_membership_collection
        self.update_metadata_collection = update_metadata_collection
        (self.con_isolates, self.cur_isolates), (self.con_seqdef, self.cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(self.species)
        self.clustering_thresholds = CLUSTERING_CONFIG[f"clustering_thresholds_{self.species}"]
        self.current_update_date = datetime.datetime.utcnow()
        self.last_date_of_update = self._get_last_date_of_update()
        if self.last_date_of_update == None:
            self.last_date_of_update = datetime.datetime(1970, 1, 1)
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
        return self.st_collection.find_one({'ID': 'headers'})

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
        for scheme_loci in ordered_by_scheme_dict.keys():
            scheme, locus = scheme_loci.split(',')
            # fetch all alleles ids already in bigs
            sqlquery = """SELECT allele_id FROM sequences WHERE locus=%s;"""
            self.cur_seqdef.execute(sqlquery, (locus,))
            listoftuples: list = self.cur_seqdef.fetchall()
            list_alleleid: list = [x[0] for x in listoftuples]
            for new_allele in ordered_by_scheme_dict[scheme_loci]:
                if new_allele['temp_allele_name'] not in list_alleleid:
                    sqlquery = """
                               INSERT INTO sequences(locus, allele_id, sequence, status, sender, 
                               curator, date_entered, datestamp) 
                               VALUES(%s, %s, %s, 'unchecked', 1, 
                               1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
                    self.cur_seqdef.execute(sqlquery, (locus, new_allele['temp_allele_name'], new_allele['allele_sequence']))
                    logging.info(f"id {new_allele['temp_allele_name']} inserted into locus {locus}")

    def _order_sequences_by_locus(self) -> Dict[str, str]:
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
        self.cur_seqdef.execute(f"SELECT MAX(profile_id) FROM profiles WHERE "
                                f"scheme_id=(SELECT id FROM schemes WHERE name='cgMLST') AND "
                                f"LENGTH(profile_id)="
                                f"(SELECT MAX(LENGTH(profile_id)) FROM profiles WHERE scheme_id=(SELECT id FROM schemes WHERE name = 'cgMLST'))")
        max_st_in_bigs = self.cur_seqdef.fetchall()[0][0]
        if max_st_in_bigs is None:
            max_st_in_bigs = 0
        for st in self.new_st:
            if int(st['cgST']) > int(max_st_in_bigs):
                logging.info(f"start insert of {st['cgST']}")
                st_id = st['cgST']
                # insertion of the st id into the profiles table
                sqlquery = """
                           INSERT INTO profiles(scheme_id, 
                           profile_id, sender, curator, 
                           date_entered, datestamp) 
                           VALUES((SELECT id FROM schemes WHERE name = 'cgMLST'), 
                           %s, 1, 1, 
                           (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
                self.cur_seqdef.execute(sqlquery, (st_id,))
                # insertion of the st in the profiles_fields
                sqlquery = """
                           INSERT INTO profile_fields(scheme_id, 
                           scheme_field, profile_id, value, 
                           curator, datestamp) 
                           VALUES((SELECT id FROM schemes WHERE name='cgMLST'), 
                           'cgST', %s, %s, 
                           1, (SELECT CURRENT_DATE));"""
                self.cur_seqdef.execute(sqlquery, (st_id, st_id))
                alleles = st['cgMLST'].split(',')
                for locus, allele_id in zip(self.st_headers['headers'], alleles):
                    if allele_id == '0':  # this will create a ForeignKeyViolation error so we prevent this
                        # by inserting a null allele if not yet present
                        sqlquery = """
                                   SELECT count(*) FROM sequences WHERE 
                                   locus=%s AND sequence='null allele';"""
                        self.cur_seqdef.execute(sqlquery, (locus,))
                        nullpresent = self.cur_seqdef.fetchall()
                        if nullpresent[0][0] == 0:
                            sqlquery = """
                                       INSERT INTO sequences(locus, allele_id, sequence, sender, curator, date_entered, datestamp) \
                                       VALUES(%s, 0, 'null allele', 0, 0, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
                            self.cur_seqdef.execute(sqlquery, (locus,))

                    sqlquery = """
                               INSERT INTO profile_members(scheme_id, 
                               locus, profile_id, allele_id, curator, datestamp) 
                               VALUES((SELECT id FROM schemes WHERE name='cgMLST'), 
                               %s, %s, %s, 1, (SELECT CURRENT_DATE));"""
                    self.cur_seqdef.execute(sqlquery, (locus, st_id, allele_id))


    def _insert_or_update_clustering(self) -> None:
        """
        Insert or update new cluster memberships retrieved during the initialization into BIGSdb. In addition, if a
        cluster is merged, the cluster membership modification is also recorded into BIGSdb
        (classification_group_profile_history table).
        :return: None.
        """
        groups_merged = []
        self.__check_for_classification_schemes()
        for cl_membership in self.new_cluster_membership:
            cg_scheme_id = self.clustering_thresholds.index(cl_membership['threshold']) + 1
            profile_id = cl_membership['cgST']
            group_id = cl_membership['clustering_membership']
            sqlquery = """SELECT * FROM classification_groups WHERE cg_scheme_id=%s AND group_id=%s;"""
            self.cur_seqdef.execute(sqlquery, (cg_scheme_id, group_id))
            query_group_exists = self.cur_seqdef.fetchall()
            if not query_group_exists:
                sqlquery = """
                           INSERT INTO classification_groups(cg_scheme_id, group_id, active, curator, datestamp) 
                           VALUES(%s, %s, true, 1, (SELECT CURRENT_DATE));"""
                self.cur_seqdef.execute(sqlquery, (cg_scheme_id, group_id))
            # group exists so now need to check if clustering membership already present
            sqlquery = """SELECT group_id FROM classification_group_profiles WHERE cg_scheme_id=%s AND profile_id=%s;"""
            self.cur_seqdef.execute(sqlquery, (cg_scheme_id, profile_id))
            query_group_profile_exists = self.cur_seqdef.fetchall()
            previous_group = query_group_profile_exists
            if not previous_group:
                sqlquery = """
                           INSERT INTO classification_group_profiles(cg_scheme_id, group_id, profile_id, 
                           scheme_id, curator, datestamp) 
                           VALUES(%s, %s, %s, 
                           (SELECT id FROM schemes WHERE name = 'cgMLST'), 1, (SELECT CURRENT_DATE));"""
                self.cur_seqdef.execute(sqlquery, (cg_scheme_id, group_id, profile_id))
            elif previous_group[0][0] != group_id:
                sqlquery = """
                           UPDATE classification_group_profiles SET group_id = %s 
                           WHERE cg_scheme_id=%s AND profile_id=%s;"""
                self.cur_seqdef.execute(sqlquery, (group_id, cg_scheme_id, profile_id))
                sqlquery = """
                           INSERT INTO classification_group_profile_history(timestamp, scheme_id, 
                           profile_id, cg_scheme_id, previous_group) 
                           VALUES((SELECT CURRENT_DATE), (SELECT id FROM schemes WHERE name = 'cgMLST'),
                           %s, %s, %s);"""
                self.cur_seqdef.execute(sqlquery, (profile_id, cg_scheme_id, previous_group[0][0]))
                if previous_group[0][0] not in groups_merged:
                    logging.debug(f'group {previous_group[0][0]} is merged into {group_id}')
                    groups_merged.append(previous_group[0][0])
                    # update group table
                    sqlquery = """UPDATE classification_groups SET active = false WHERE cg_scheme_id=%s AND group_id=%s;"""
                    self.cur_seqdef.execute(sqlquery, (profile_id, previous_group[0][0]))

    def __check_for_classification_schemes(self) -> None:
        """
        Check if the classification schemes are already into BIGSdb. if not, insert them.
        :return:
        """
        self.cur_seqdef.execute(f"SELECT id, inclusion_threshold from classification_schemes")
        query_res = self.cur_seqdef.fetchall()
        thresholds_presents = [x[1] for x in query_res]
        idx_max = max([x[0] for x in query_res])
        for threshold in self.clustering_thresholds:
            if threshold not in thresholds_presents:
                name = f"cgMLST_{threshold}_diffs_clustering"
                description = f"Clustering of the cgMLST profiles at {threshold} alleles of differences"
                # initialize in seqdef
                sqlquery = """
                           INSERT INTO classification_schemes(id, scheme_id, name, description, inclusion_threshold, 
                           use_relative_threshold, display_order, status, curator, datestamp) 
                           VALUES(%s, (SELECT id FROM schemes WHERE name = 'cgMLST'), %s, %s, %s, 
                           false, %s, 'experimental', 1, (SELECT CURRENT_DATE));"""
                self.cur_seqdef.execute(sqlquery, (idx_max + 1, name, description, threshold, idx_max + 1))
                # initialize in isolates
                sqlquery = """
                           INSERT INTO classification_schemes(id, scheme_id, name, description, inclusion_threshold, 
                           use_relative_threshold, seqdef_cscheme_id, display_order, status, curator, datestamp) 
                           VALUES(%s, (SELECT id FROM schemes WHERE name = 'cgMLST'), %s, %s, %s, 
                           false, %s, %s, 'experimental', 1, (SELECT CURRENT_DATE));"""
                self.cur_seqdef.execute(sqlquery, (idx_max + 1, name, description, threshold, idx_max + 1, idx_max + 1))
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
    mongoinit = MongoInitialisation()
    hashed_ad_collection = mongoinit.initialise_hashing_collection(config_data, species)
    st_collection, cluster_membership_collection, cluster_merging_collection = \
        mongoinit.initialise_clustering_collections(config_data, species)
    update_collection = mongoinit.initialise_update_collection(config_data, species)

    # initialize the class
    try:
        updater = NewAllelesProfileClusteringFromMongoToBigs(species, st_collection, hashed_ad_collection,
                                        cluster_membership_collection, update_collection)
        updater.insert_into_bigs()
    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        raise Exception(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}")
