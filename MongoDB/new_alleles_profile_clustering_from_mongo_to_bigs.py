import sys
import yaml
import argparse
import logging
from pymongo.write_concern import WriteConcern
import datetime
from datetime import date
import smtplib
from email.message import EmailMessage
import socket
import traceback
import os

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from MongoDB.util.mongo_initialisation import Mongoinitialisation
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
    def __init__(self, species: str, st_collection: object, hashed_ad_collection: object, cluster_membership_collection: object,
                 update_metadata_collection: object) -> None:
        """
        Initialization of the class.
        :param species: the species that needs to be updated
        :param st_collection: the sequence type collection from the mongo db of the species
        :param hashed_ad_collection: the ashed allele collection of mongo db of the species
        :param cluster_membership_collection: cluster membership collection from the mongo db of the species
        :param update_metadata_collection: the update metadata collection from the mongo db of the species
        """
        self.species = species
        self.schemes = ['mlst', 'cgmlst'] if species != 'stec' else ['mlst_warwick', 'mlst_pasteur', 'cgmlst']
        self.schemedict = {
            'listeria': {'seqdefdb': 'bigsdb_listeria_seqdef', 'isolatedb': 'bigsdb_listeria_isolates'},
            'mycobacterium': {'seqdefdb': 'bigsdb_mycobacterium_seqdef', 'isolatedb': 'bigsdb_mycobacterium_isolates'},
            'neisseria': {'seqdefdb': 'bigsdb_neisseria_seqdef', 'isolatedb': 'bigsdb_neisseria_isolates'},
            'stec': {'seqdefdb': 'bigsdb_stec_seqdef', 'isolatedb': 'bigsdb_stec_isolates'},
            'salmonella': {'seqdefdb': 'bigsdb_salmonella_seqdef', 'isolatedb': 'bigsdb_salmonella_isolates'}
        }
        self.st_collection = st_collection
        self.hashed_ad_collection = hashed_ad_collection
        self.cluster_membership_collection = cluster_membership_collection
        self.update_metadata_collection = update_metadata_collection
        self.cur_isolates, self.cur_seqdef = DatabaseConnection().open_database_connections(self.species)
        self.clustering_thresholds = CLUSTERING_CONFIG[f"clustering_thresholds_{self.species}"]
        self.current_update_date = datetime.datetime.utcnow()
        self.last_date_of_update = self._get_last_date_of_update()
        if self.last_date_of_update == None:
            self.last_date_of_update = datetime.datetime(1970, 1, 1)
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

    def _get_st_headers(self) -> dict:
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
            self.cur_seqdef.execute(f"SELECT allele_id FROM sequences WHERE locus='{locus}'")
            rows = self.cur_seqdef.fetchall()
            list_alleleid = []
            for item in rows:
                list_alleleid.append(item[0])
            for new_allele in ordered_by_scheme_dict[scheme_loci]:
                if new_allele['temp_allele_name'] not in list_alleleid:
                    try:
                        self.cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,"
                                                f"curator, date_entered, datestamp) VALUES('{locus}',"
                                                f"'{new_allele['temp_allele_name']}','{new_allele['allele_sequence']}',"
                                                f"'unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        print(f"id {new_allele['temp_allele_name']} inserted into locus {locus}")
                    except:
                        self.cur_seqdef.execute(
                            f"SELECT allele_id FROM sequences WHERE allele_id='{new_allele['temp_allele_name']}'")
                        test = self.cur_seqdef.fetchall()
                        test_list = []
                        for it in test:
                            test_list.append(it)
                        if len(test_list) > 0:
                            print(f"id {new_allele['temp_allele_name']} already inserted = no insertion required")
                        else:
                            LookupError(
                                f"id {new_allele['temp_allele_name']} is not inserted in the db and wasn't found in the db"
                                f". Please investigate this error further!")

    def _order_sequences_by_locus(self) -> dict:
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
                                f"scheme_id = (SELECT id FROM schemes WHERE name = 'cgMLST') AND "
                                f"LENGTH(profile_id) = (SELECT MAX(LENGTH(profile_id)) FROM profiles WHERE scheme_id = "
                                f"(SELECT id FROM schemes WHERE name = 'cgMLST'))")
        max_st_in_bigs = self.cur_seqdef.fetchall()[0][0]
        if max_st_in_bigs is None:
            max_st_in_bigs = 0
        for st in self.new_st:
            if int(st['cgST']) > int(max_st_in_bigs):
                print(f"start insert of {st['cgST']}")
                st_id = st['cgST']
                # insertion of the st id into the profiles table
                self.cur_seqdef.execute(f"INSERT INTO profiles(scheme_id, "
                                        f"profile_id, sender, curator, "
                                        f"date_entered, datestamp) "
                                        f"VALUES((SELECT id FROM schemes WHERE name = 'cgMLST'),"
                                        f"'{st_id}', 1, 1, "
                                        f"(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                # insertion of the st in the profiles_fields
                self.cur_seqdef.execute(f"INSERT INTO profile_fields(scheme_id, "
                                        f"scheme_field, profile_id, value, "
                                        f"curator, datestamp) "
                                        f"VALUES((SELECT id FROM schemes WHERE name = 'cgMLST'),"
                                        f"'cgST', '{st_id}', '{st_id}', "
                                        f"1,(SELECT CURRENT_DATE))")
                alleles = st['cgMLST'].split(',')
                for locus, allele_id in zip(self.st_headers['headers'], alleles):
                    if allele_id == '0':  # this will create a ForeignKeyViolation error so we prevent this
                        # by inserting a null allele if not yet present
                        self.cur_seqdef.execute(f"SELECT count(*) FROM sequences WHERE "
                                                f"locus = '{locus}' AND sequence = 'null allele'")
                        nullpresent = self.cur_seqdef.fetchall()
                        if nullpresent[0][0] == 0:
                            self.cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status, sender,"
                                                    f"curator, date_entered, datestamp)VALUES('{locus}',0, "
                                                    f"'null allele', '',0,0,(SELECT CURRENT_DATE),"
                                                    f"(SELECT CURRENT_DATE))")


                    self.cur_seqdef.execute(f"INSERT INTO profile_members(scheme_id, "
                                                f"locus, profile_id, allele_id, "
                                                f"curator, datestamp) "
                                                f"VALUES((SELECT id FROM schemes WHERE name = 'cgMLST'),"
                                                f"'{locus}', '{st_id}', '{allele_id}', "
                                                f"1,(SELECT CURRENT_DATE))")


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
            self.cur_seqdef.execute(
                f"SELECT * FROM classification_groups WHERE (cg_scheme_id = '{cg_scheme_id}' and"
                f" group_id = '{group_id}')")
            test_group_exist = self.cur_seqdef.fetchall()
            if not test_group_exist:
                self.cur_seqdef.execute(
                    f"INSERT INTO classification_groups (cg_scheme_id, group_id, active, curator, datestamp)"
                    f"VALUES ('{cg_scheme_id}', '{group_id}', true, 1, (SELECT CURRENT_DATE))")
            # group exists so now need to check if clustering membership already present
            self.cur_seqdef.execute(
                f"SELECT group_id FROM classification_group_profiles WHERE (cg_scheme_id = '{cg_scheme_id}'"
                f" and profile_id = '{profile_id}')")
            test_group_profile_exist = self.cur_seqdef.fetchall()
            previous_group = test_group_profile_exist
            if not previous_group:
                self.cur_seqdef.execute(
                    f"INSERT INTO classification_group_profiles (cg_scheme_id, group_id, profile_id, scheme_id, "
                    f"curator, datestamp) VALUES ('{cg_scheme_id}', '{group_id}','{profile_id}',"
                    f" (SELECT id FROM schemes WHERE name = 'cgMLST'), 1, (SELECT CURRENT_DATE))")
            elif previous_group[0][0] != group_id:
                self.cur_seqdef.execute(
                    f"UPDATE classification_group_profiles SET group_id = '{group_id}' WHERE"
                    f" cg_scheme_id = '{cg_scheme_id}' AND profile_id = '{profile_id}'")
                self.cur_seqdef.execute(
                    f"INSERT INTO classification_group_profile_history (timestamp, scheme_id, profile_id, cg_scheme_id,"
                    f" previous_group, comment)VALUES ((SELECT CURRENT_DATE), (SELECT id FROM schemes WHERE"
                    f" name = 'cgMLST'), '{profile_id}', '{cg_scheme_id}', '{previous_group[0][0]}', 'n.c.')")
                if previous_group[0][0] not in groups_merged:
                    print(f'group {previous_group[0][0]} is merged into {group_id}')
                    groups_merged.append(previous_group[0][0])
                    # update group table
                    self.cur_seqdef.execute(
                        f"UPDATE classification_groups SET active = false WHERE cg_scheme_id = '{cg_scheme_id}' AND \
                                                          group_id = '{previous_group[0][0]}'")

    def __check_for_classification_schemes(self) -> None:
        """
        Check if the classification schemes are already into BIGSdb. if not, insert them.
        :return:
        """
        self.cur_seqdef.execute(f"SELECT id,inclusion_threshold from classification_schemes")
        query_res = self.cur_seqdef.fetchall()
        if query_res[0][0] is not None:
            thresholds_presents = [x[1] for x in query_res]

        else:
            thresholds_presents = []
        idx_max = len(thresholds_presents)
        for threshold in self.clustering_thresholds:
            if threshold not in thresholds_presents:
                name = f"cgMLST_{threshold}_diffs_clustering"
                description = f"Clustering of the cgMLST profiles at {threshold} alleles of differences"
                # initialize in seqdef
                self.cur_seqdef.execute(
                    f"INSERT INTO classification_schemes (id, scheme_id, name, description, inclusion_threshold,"
                    f" use_relative_threshold, display_order, status, curator, datestamp)VALUES ('{idx_max + 1}', "
                    f"(SELECT id FROM schemes WHERE name = 'cgMLST'), '{name}', '{description}', '{threshold}',"
                    f" false, '{idx_max + 1}', 'experimental',1, (SELECT CURRENT_DATE) )")
                # initialize in isolates
                self.cur_isolates.execute(
                    f"INSERT INTO classification_schemes (id, scheme_id, name, description, inclusion_threshold, "
                    f"use_relative_threshold, seqdef_cscheme_id, display_order, status, curator, datestamp) "
                    f"VALUES ('{idx_max + 1}', (SELECT id FROM schemes WHERE name = 'cgMLST'), '{name}', '{description}',"
                    f" '{threshold}', false, '{idx_max + 1}','{idx_max + 1}', 'experimental',1, (SELECT CURRENT_DATE) )")
                idx_max += 1
            else:
                print(f"Threshold {threshold} already present")


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
    mongoinit = Mongoinitialisation()
    hashed_ad_collection = mongoinit.initialise_hashing_collection(config_data, species)
    st_collection, cluster_membership_collection = \
        mongoinit.initialise_clustering_collections(config_data, species)
    update_collection = mongoinit.initialise_update_collection(config_data, species)

    # initialize the class
    try:
        updater = NewAllelesProfileClusteringFromMongoToBigs(species, st_collection, hashed_ad_collection,
                                        cluster_membership_collection, update_collection)
        updater.insert_into_bigs()
    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)}: mongo to bigs fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])