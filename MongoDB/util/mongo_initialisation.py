import abc
from pymongo import MongoClient
import logging


class Mongoinitialisation:
    """
    Class containing all queries for Mongo
    """

    def __init__(self):
        pass

    def _open_mongo_database(self, config_data, species) -> object:
        """
        Connects to the mongo Cloud Cluster specified in the config file and opens the database
        :param config_data:
        :param species:
        :return: opened database object
        """
        try:
            client = MongoClient(config_data["CONNECTION_STRING_BASE"])
        except:
            raise RuntimeError(f"Could not connect to {config_data['CONNECTION_STRING_BASE']}")
        return client[species]

    def _open_mongo_collection(self, opened_database, collection: str) -> object:
        """
        Opens a mongo collection in an opened database
        :param opened_database: mongo opened database
        :param collection: mongo collection to be opened
        :return: opened collection object
        """
        # MongoDB creates collections on the fly while inserting any Documents, we do not want to allow unwanted collections to be created, therefore this check:
        if collection in ["isolates", "old_isolate_results", "isolates_badqc", "sequence_types", "new_allele_hashes", "cluster_membership", "new_allele_hashes"]:
            opened_collection = opened_database[collection]
            logging.debug(f"opened collection {collection}")
            return opened_collection
        else:
            raise RuntimeError(f"Collection '{collection}' not in supported collections")

    def _initialise_collections(self, config_data: dict, species: str) -> object:
        """
        Initialises database and collections for interaction
        :param config_data: config data that contains connection string connect to Cloud Cluster or local
        :param species: string that is the database name
        :return: opened isolate, isolatesresults and isolatesbadqc collections (objects) for a given species
        """
        # open connection to species db
        species_database = self._open_mongo_database(config_data, species)
        # open isolates collection
        isolates_collection = self._open_mongo_collection(species_database, "isolates")
        # open isolate_results collection
        isolateresults_collection = self._open_mongo_collection(species_database, "old_isolate_results")
        # open isolates badqc collection
        isolates_badqc_collection = self._open_mongo_collection(species_database, "isolates_badqc")
        return isolates_collection, isolateresults_collection, isolates_badqc_collection

    def initialise_clustering_collections(self, config_data: dict, species: str):
        """
        Initialises database and collections for interaction
        :param config_data: config data to connect to Cloud Cluster
        :param species: string that is the database name
        :return: opened sequence_type and  for a given species
        """
        species_database = self._open_mongo_database(config_data, species)
        st_collection = self._open_mongo_collection(species_database, "sequence_types")
        cluster_membership_collection = self._open_mongo_collection(species_database, "cluster_membership")
        return st_collection,  cluster_membership_collection

    def initialise_hashing_collection(self, config_data: dict, species: str) -> object:
        """
        :param config_data:
        :param species:
        :return: Opened hashing collection
        """
        species_database = self._open_mongo_database(config_data, species)
        hashed_AD_collection = self._open_mongo_collection(species_database, "new_allele_hashes")
        return hashed_AD_collection
