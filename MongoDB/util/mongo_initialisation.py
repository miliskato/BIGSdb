import abc
from pymongo import MongoClient
import logging

class Mongoinitialisation(object, metaclass=abc.ABCMeta):
    """
    Class containing all queries for Mongo
    """
    def __init__(self):
        pass

    def _open_mongo_database(self, config_data, species) -> None:
        """
        Connects to the mongo Cloud Cluster specified in the config file and opens the database
        :param config_data:
        :param species:
        :return: opened database
        """
        try:
            client = MongoClient(config_data["CONNECTION_STRING_BASE"])
        except:
            raise RuntimeError(f"Could not connect to {config_data['CONNECTION_STRING_BASE']}")
        # todo change the test
        return client[f"{species}_test"]

    def _open_mongo_collection(self, opened_database, collection: str) -> None:
        """
        Opens a mongo collection in an opened database
        :param opened_database: mongo opened database
        :param collection: mongo collection to be opened
        :return: opened collection
        """
        # MongoDB creates collections on the fly while inserting any Documents, we do not want to allow unwanted collections to be created, therefore this check:
        if collection in ["isolates", "isolate_results"]:
            opened_collection = opened_database[collection]
            logging.debug(f"opened collection {collection}")
            return opened_collection
        else:
            raise RuntimeError(f"Collection '{collection}' not in supported collections")

    def _initialise_collections(self, config_data: dict, species: str) -> None:
        """
        Initialises database and collections for interaction
        :param config_data: config data to connect to Cloud Cluster
        :param species: string that is the database name
        :return: opened isolate and isolatescollection for a given species
        """
        # open connection to species db
        species_database = self._open_mongo_database(config_data, species)
        # open isolates collection
        isolates_collection = self._open_mongo_collection(species_database, "isolates")
        # open isolate_results collection
        isolateresults_collection = self._open_mongo_collection(species_database, "isolate_results")
        return isolates_collection, isolateresults_collection