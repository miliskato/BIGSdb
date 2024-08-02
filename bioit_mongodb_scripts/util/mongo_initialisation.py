import logging
from typing import Any, Dict, Union

import pymongo
from pymongo import MongoClient, database

from .python_utility_functions import get_mongodb_config_data


class MongoInitialisation:
    """
    Class containing all queries for Mongo
    """
    def __init__(self, species: str, alternate_connection_string: Union[bool, str] = False, alternate_dtap:
                 Union[str, None] = None, mongo_config_data: Dict[str, Any] = None):
        """
        Initialises this class and opens the species/dtap specific mongo database
        :param species: commonly used bioit species name: either genus or specific like stec
        :param alternate_connection_string: Use the alternate connection string, which connects to the testing Atlas Cluster or provide a custom connection string
        :param alternate_dtap: alternative dtap than what is in the config file
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        """
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()
        if isinstance(alternate_connection_string, bool) and alternate_connection_string:
            self._mongo_config_data['CONNECTION_STRING_AZURE'] = self._mongo_config_data['CONNECTION_STRING_ALTERNATE']
        elif isinstance(alternate_connection_string, str):
            self._mongo_config_data['CONNECTION_STRING_AZURE'] = alternate_connection_string
        if alternate_dtap:
            self._mongo_config_data['dtap'] = alternate_dtap
        self.opened_mongo_database = self._open_mongo_database(species)

    def _open_mongo_database(self, species: str) -> pymongo.database.Database:
        """
        Connects to the mongo Cloud Cluster specified in the config file and opens the database
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: opened database object
        """
        try:
            self.client = MongoClient(self._mongo_config_data["CONNECTION_STRING_AZURE"])
        except Exception:
            raise RuntimeError(f"Could not connect to {self._mongo_config_data['CONNECTION_STRING_AZURE']}")
        if self._mongo_config_data["dtap"] not in ['dev', 'test', 'acc', 'prod']:
            raise NameError(f"replace dtap value in bioit_mongodb_scripts/config/config.yml or use alternate_dtap")
        return self.client['_'.join([species, self._mongo_config_data["dtap"]])]  # e.g. listeria_dev

    def _open_mongo_collection(self, opened_database: pymongo.database.Database, collection: str) -> pymongo.collection.Collection:
        """
        Opens a mongo collection in an opened database
        :param opened_database: mongo opened database
        :param collection: mongo collection to be opened
        :return: opened collection object
        """
        # MongoDB creates collections on the fly while inserting any Documents, we do not want to allow
        # unwanted collections to be created, therefore this check:
        if collection in self._mongo_config_data['collections']:
            opened_collection = opened_database[collection]
            logging.debug(f"opened collection {collection}")
            return opened_collection
        else:
            raise RuntimeError(f"Collection '{collection}' not in supported collections")

    def initialise_collections(self) -> (pymongo.collection.Collection, pymongo.collection.Collection, pymongo.collection.Collection, pymongo.collection.Collection):
        """
        Initialises database and collections for interaction
        :return: opened isolate, isolatesresults, isolatesbadqc, and isolates resequencing collections (instances) for a given species
        """
        # open isolates collection
        isolates_collection = self._open_mongo_collection(self.opened_mongo_database, "isolates")
        # open isolate_results collection
        isolateresults_collection = self._open_mongo_collection(self.opened_mongo_database, "old_isolate_results")
        # open isolates badqc collection
        isolates_badqc_collection = self._open_mongo_collection(self.opened_mongo_database, "isolates_badqc")
        # open isolates resequencing collection
        isolates_resequencing_collection = self._open_mongo_collection(self.opened_mongo_database, "isolates_resequencing")
        return isolates_collection, isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection

    def initialise_clustering_collections(self) -> (pymongo.collection.Collection, pymongo.collection.Collection, pymongo.collection.Collection):
        """
        Initialises database and collections for interaction
        :return: opened sequence_type, cluster membership, and cluster merging history collections for a given species
        """
        st_collection = self._open_mongo_collection(self.opened_mongo_database, "sequence_types")
        cluster_membership_collection = self._open_mongo_collection(self.opened_mongo_database, "cluster_membership")
        cluster_merging_collection = self._open_mongo_collection(self.opened_mongo_database, "cluster_merging")
        return st_collection,  cluster_membership_collection, cluster_merging_collection

    def initialise_hashing_collection(self) -> pymongo.collection.Collection:
        """
        Initialises collection containing hashes
        :return: Opened hashing collection
        """
        hashed_ad_collection = self._open_mongo_collection(self.opened_mongo_database, "new_allele_hashes")
        return hashed_ad_collection

    def initialise_update_collection(self) -> pymongo.collection.Collection:
        """
        Initialises collection containing update metadata
        :return: Opened update metadata collection
        """
        update_collection = self._open_mongo_collection(self.opened_mongo_database, "update_metadata")
        return update_collection

    def initialise_headers_collection(self) -> pymongo.collection.Collection:
        """
        Initialises collection containing headers of all sorts:
        typing hit dictionary headers,
        cgST profile headers,
        ...
        :return: Opened headers collection
        """
        headers_collection = self._open_mongo_collection(self.opened_mongo_database, "headers")
        return headers_collection

    def initialise_mapping_table_collection(self) -> pymongo.collection.Collection:
        """
        Initialises collection containing mapping table of sample names and pseudonymized sample names.
        :return: Opened mapping table collection
        """
        headers_collection = self._open_mongo_collection(self.opened_mongo_database, "mapping_table")
        return headers_collection
