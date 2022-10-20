import sys
import yaml
import argparse
import logging
from pymongo.write_concern import WriteConcern
import datetime
from datetime import date
from bioit_custom_scripts.components.databaseconnection import Database_connection
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.config import HIERCC_CONFIG


class NewAllelesFromMongoToBigs:
    def __init__(self, species: str, st_collection, hashed_AD_collection, cluster_membership_collection,
                 update_metadata_collection):
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
        self.hashed_AD_collection = hashed_AD_collection
        self.cluster_membership_collection = cluster_membership_collection
        self.update_metadata_collection = update_metadata_collection
        self.cur_isolates, self.cur_seqdef = Database_connection().open_database_connections(self.species)
        self.clustering_thresholds = HIERCC_CONFIG["clustering_thresholds"]
        self.current_update_date = datetime.datetime.utcnow()
        self.last_date_of_update = self._get_last_date_of_update()
        self.new_sequences = self._get_new_sequence()
        self.new_st = self._get_new_st()
        self.st_headers = self._get_st_headers()
        self.new_cluster_membership = self._get_new_cluster_membership()

    def _get_last_date_of_update(self) -> date:
        return self.update_metadata_collection.find_one({'metadata': 'last_update'})['last_update_date']

    @staticmethod
    def _extract_mongo_query(query) -> list:
        result = []
        for doc in query:
            result.append(doc)
        return result

    def _get_new_sequence(self) -> list:
        query_seq = self.hashed_AD_collection.find({'insertion_date': {'$gt': self.last_date_of_update}})
        results = self._extract_mongo_query(query_seq)
        return results

    def _get_new_st(self) -> list:
        query_st = self.st_collection.find({'insertion_date': {'$gt': self.last_date_of_update}})
        sts = self._extract_mongo_query(query_st)
        return sts

    def _get_st_headers(self) -> dict:
        return self.st_collection.find_one({'ID': 'headers'})

    def _get_new_cluster_membership(self) -> list:
        query_cluster = self.cluster_membership_collection.find({'insertion_date': {'$gt': self.last_date_of_update}})
        cluster = self._extract_mongo_query(query_cluster)
        return cluster

    def insert_into_bigs(self) -> None:
        if len(self.new_sequences) > 0:
            print('new sequences are being inserted')
            self._insert_new_alleles()
        if len(self.new_st) > 0:
            print('new sequence types are being inserted')
            self._insert_sequence_types()

        # self._update_last_update_date()

    def _insert_new_alleles(self) -> None:
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
                if new_allele['allele_number'] not in list_alleleid:
                    try:
                        self.cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                                          VALUES('{locus}','{new_allele['allele_number']}','{new_allele['allele_sequence']}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
                        print(f"id {new_allele['allele_number']} inserted into locus {locus}")
                    except:
                        self.cur_seqdef.execute(
                            f"SELECT allele_id FROM sequences WHERE allele_id='{new_allele['allele_number']}'")
                        test = self.cur_seqdef.fetchall()
                        test_list = []
                        for it in test:
                            test_list.append()
                        if len(test_list) > 0:
                            print(f"id {new_allele['allele_number']} already inserted = no insertion required")
                        else:
                            LookupError(
                                f"id {new_allele['allele_number']} is not inserted in the db and wasn't found in the db. Please investigate this error further!")

    def _order_sequences_by_locus(self) -> dict:
        order_seqs = {}
        for seq in self.new_sequences:
            key = f"{seq['scheme']},{seq['locus']}"
            if key in order_seqs:
                order_seqs[key].append(seq)
            else:
                order_seqs[key] = [seq]
        return order_seqs

    def _insert_sequence_types(self):
        self.cur_seqdef.execute(f"SELECT MAX(profile_id) FROM profiles WHERE "
                                f"scheme_id = (SELECT id FROM schemes WHERE name = 'cgMLST') AND "
                                f"LENGTH(profile_id) = (SELECT MAX(LENGTH(profile_id)) FROM profiles WHERE scheme_id = (SELECT id FROM schemes WHERE name = 'cgMLST'))")
        max_st_in_bigs = self.cur_seqdef.fetchall()[0][0]
        if max_st_in_bigs is None:
            max_st_in_bigs = 0
        for st in self.new_st:
            if int(st['ST']) > int(max_st_in_bigs):
                st_id = st['ST']
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
                    if allele_id == '0':  # this will create a ForeignKeyViolation error so we prevent this by inserting a null allele if not yet present
                        self.cur_seqdef.execute(f"SELECT count(*) FROM sequences WHERE "
                                        f"locus = '{locus}' AND sequence = 'null allele'")
                        nullpresent = self.cur_seqdef.fetchall()
                        if nullpresent[0][0] == 0:
                            self.cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status, sender,curator, date_entered, datestamp) \
                                          VALUES('{locus}',0, 'null allele', '',0,0,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

                    try:
                        self.cur_seqdef.execute(f"INSERT INTO profile_members(scheme_id, "
                                    f"locus, profile_id, allele_id, "
                                    f"curator, datestamp) "
                                    f"VALUES((SELECT id FROM schemes WHERE name = 'cgMLST'),"
                                    f"'{locus}', '{st_id}', '{allele_id}', "
                                    f"1,(SELECT CURRENT_DATE))")
                    except:
                        logging.error(
                            f"profile with field cgST and value {st_id} already exists as another field, either remove the entire scheme profiles or find out what the exact problem is and solve this script once and for all with delete where select profile_id where locus1 and alleleid1 intersect select ... (e.g. select profile_id from profile_members where (locus='abcZ' and allele_id='1') INTERSECT select profile_id from profile_members where (locus='bglA' and allele_id='1') INTERSECT select profile_id from profile_members where (locus='cat' and allele_id='1'))")
                        continue

    def _insert_or_update_clustering(self):
        groups_merged = []
        self._check_for_classification_schemes()
        for cl_membership in self.new_cluster_membership:
            cg_scheme_id = self.clustering_thresholds.index(cl_membership['Threshold'])+1
            profile_id = cl_membership['ST']
            group_id = cl_membership['Clustering_membership']
            self.cur_seqdef.execute(f"SELECT * FROM classification_groups WHERE (cg_scheme_id = '{cg_scheme_id}' and group_id = '{group_id}')")
            test_group_exist = self.cur_seqdef.fetchall()
            if test_group_exist[0][0] is None:
                self.cur_seqdef.execute(f"INSERT INTO classification_groups (cg_scheme_id, group_id, active, curator, datestamp)"
                                        f"VALUES ('{cg_scheme_id}', '{group_id}', true, 1, (SELECT CURRENT_DATE))")
            # group exists so now need to check if clustering membership already present
            self.cur_seqdef.execute(
                f"SELECT group_id FROM classification_group_profiles WHERE (cg_scheme_id = '{cg_scheme_id}' and profile_id = '{profile_id}')")
            test_group_profile_exist = self.cur_seqdef.fetchall()
            print(test_group_profile_exist[0][0])
            if test_group_profile_exist[0][0] is None:
                self.cur_seqdef.execute(f"INSERT INTO classification_group_profiles (cg_scheme_id, group_id, profile_id, scheme_id, curator, datestamp)"
                                        f"VALUES ('{cg_scheme_id}', '{group_id}','{profile_id}', (SELECT id FROM schemes WHERE name = 'cgMLST'), 1, (SELECT CURRENT_DATE))")
            else:
                groups_merged.append(test_group_profile_exist[0][0])
                self.cur_seqdef.execute(f"UPDATE classification_group_profiles SET group_id = '{group_id}' WHERE cg_scheme_id = '{cg_scheme_id}' AND \
                                      profile_id = '{profile_id}'")
        groups_merged = list(set(groups_merged))
        #todo : change the value of the group to false in the end and add in the history table (classification_group_profile_history) the change of group that happened


    def _check_for_classification_schemes(self):
        self.cur_seqdef.execute(f"SELECT id from classification_schemes")
        query_res = self.cur_seqdef.fetchall()[0][0]
        if query_res is None:
            #no classification schemes, create them.
            for idx, threshold in enumerate(self.clustering_thresholds):
                name = f"cgMLST_{threshold}_diffs_clustering"
                description = f"Clustering of the cgMLST profiles at {threshold} alleles of differences"
                #initialize in seqdef
                self.cur_seqdef.execute(f"INSERT INTO classification_schemes (id, scheme_id, name, description, inclusion_threshold, use_relative_threshold, display_order, status, curator, datestamp)"
                                        f"VALUES ('{idx+1}', (SELECT id FROM schemes WHERE name = 'cgMLST'), '{name}', '{description}', '{threshold}', false, '{idx+1}', 'experimental',1, (SELECT CURRENT_DATE) )")
                #initialize in isolates
                self.cur_isolates.execute(
                    f"INSERT INTO classification_schemes (id, scheme_id, name, description, inclusion_threshold, use_relative_threshold, seqdef_scheme_id, display_order, status, curator, datestamp)"
                    f"VALUES ('{idx + 1}', (SELECT id FROM schemes WHERE name = 'cgMLST'), '{name}', '{description}', '{threshold}', false, '{idx + 1}','{idx + 1}', 'experimental',1, (SELECT CURRENT_DATE) )")
        else:
            print('No initialization is required')

    def _update_last_update_date(self) -> None:
        self.update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {'metadata': 'last_update'}, {
                "$set": {'last_update_date': self.current_update_date}})


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=['mycobacterium', 'listeria', 'listeria_test', 'neisseria', 'stec', 'salmonella'])
    return parser.parse_args()


if __name__ == '__main__':
    # Parse arguments
    args = parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    # Open collections
    mongoinit = Mongoinitialisation()
    hashed_AD_collection = mongoinit.initialise_hashing_collection(config_data, args.species)
    st_collection, cluster_membership_collection = \
        mongoinit.initialise_clustering_collections(config_data, args.species)
    update_collection = mongoinit.initialise_update_collection(config_data, args.species)

    # initialize the class
    updater = NewAllelesFromMongoToBigs(args.species, st_collection, hashed_AD_collection,
                                        cluster_membership_collection, update_collection)
    updater.insert_into_bigs()
