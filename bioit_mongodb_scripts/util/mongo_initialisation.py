import logging
from typing import Literal, Union

import pymongo
from pymongo import MongoClient, database
from pymongo.collection import Collection

from bioit_bigsdb_scripts.utils.literal_helper import validate_literal

MongoCollectionNames = Literal[
    "isolates",
    "old_isolate_results",
    "isolates_badqc",
    "sequence_types",
    "new_allele_hashes",
    "cluster_membership",
    "cluster_merging",
    "update_metadata",
    "isolates_resequencing",
    "headers",
    "mapping_table",
    "nominative_labtest_clinical_metadata",
    "unprocessed_nominative_labtest_metadata",
    "unprocessed_nominative_clinical_metadata",
    "isolates_rejected_coreqc"
]
MongoCollectionName = Union[str, MongoCollectionNames]  # workaround to avoid pycharm warnings - coupled with validate_literal


class MongoInitialisation:
    """
    Class containing all queries for Mongo
    """

    def __init__(self, species: str, connection_string: str, dtap: str):
        """
        Initialises this class and opens the species/dtap specific mongo database
        :param species: commonly used bioit species name: either genus or specific like stec
        :param connection_string: to select the connection string from the config file that should be used to
        initialise the connection
        :param dtap: dtap value need to be contained in dev, test, acc, or prod. If not, an error is raised.
        """
        self.connection_string = connection_string
        self._dtap = dtap
        self.opened_mongo_database = self._open_mongo_database(species)

    def _open_mongo_database(self, species: str) -> pymongo.database.Database:
        """
        Connects to the mongo Cloud Cluster specified in the config file and opens the database
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: opened database object
        """
        try:
            self.client = MongoClient(self.connection_string)
        except Exception:
            raise RuntimeError(f"Could not connect to {self.connection_string}")
        if self._dtap not in ['dev', 'test', 'acc', 'prod']:
            raise NameError(f"replace dtap value in bioit_mongodb_scripts/config/config.yml or use alternate_dtap")
        return self.client['_'.join([species, self._dtap])]  # e.g. listeria_dev

    def _open_mongo_collection(self, opened_database: pymongo.database.Database, collection: MongoCollectionName) -> Collection:
        """
        Opens a mongo collection in an opened database
        :param opened_database: mongo opened database
        :param collection: mongo collection to be opened
        :return: opened collection object
        """
        # MongoDB creates collections on the fly while inserting any Documents, we do not want to allow
        # unwanted collections to be created, therefore this check:

        validate_literal(collection, MongoCollectionNames)
        opened_collection = opened_database[str(collection)]
        logging.debug(f"opened collection {collection}")
        return opened_collection

    def initialise_collections(self) -> (Collection, Collection, Collection, Collection, Collection):
        """
        Initialises database and collections for interaction.
        :return: opened isolates, isolatesresults, isolateswarningqc, isolates resequencing and isolates goodqc
        collections (instances) for a given species.
        """
        # open isolates collection
        isolates_collection = self._open_mongo_collection(self.opened_mongo_database, "isolates")
        # open isolate_results collection
        isolateresults_collection = self._open_mongo_collection(self.opened_mongo_database, "old_isolate_results")
        # open isolates warning collection
        isolates_warningqc_collection = self._open_mongo_collection(self.opened_mongo_database, "isolates_warningqc")
        # open isolates resequencing collection
        isolates_resequencing_collection = self._open_mongo_collection(self.opened_mongo_database,
                                                                       "isolates_resequencing")
        # open isolates goodqc collection
        isolates_goodqc_collection = self._open_mongo_collection(self.opened_mongo_database, "isolates_goodqc")
        return isolates_collection, isolateresults_collection, isolates_warningqc_collection, isolates_resequencing_collection, isolates_goodqc_collection

    def initialise_clustering_collections(self) -> (Collection, Collection, Collection):
        """
        Initialises database and collections for interaction
        :return: opened sequence_type, cluster membership, and cluster merging history collections for a given species
        """
        st_collection = self._open_mongo_collection(self.opened_mongo_database, "sequence_types")
        cluster_membership_collection = self._open_mongo_collection(self.opened_mongo_database, "cluster_membership")
        cluster_merging_collection = self._open_mongo_collection(self.opened_mongo_database, "cluster_merging")
        return st_collection, cluster_membership_collection, cluster_merging_collection

    def initialise_hashing_collection(self) -> Collection:
        """
        Initialises collection containing hashes
        :return: Opened hashing collection
        """
        hashed_ad_collection = self._open_mongo_collection(self.opened_mongo_database, "new_allele_hashes")
        return hashed_ad_collection

    def initialise_update_collection(self) -> Collection:
        """
        Initialises collection containing update metadata
        :return: Opened update metadata collection
        """
        update_collection = self._open_mongo_collection(self.opened_mongo_database, "update_metadata")
        return update_collection

    def initialise_headers_collection(self) -> Collection:
        """
        Initialises collection containing headers of all sorts:
        typing hit dictionary headers,
        cgST profile headers,
        ...
        :return: Opened headers collection
        """
        headers_collection = self._open_mongo_collection(self.opened_mongo_database, "headers")
        return headers_collection

    def initialise_mapping_table_collection(self) -> Collection:
        """
        Initialises collection containing mapping table of sample names and pseudonymized sample names and
        business keys.
        :return: Opened mapping table collection
        """
        mapping_table_collection = self._open_mongo_collection(self.opened_mongo_database, "mapping_table")
        return mapping_table_collection

    def initialise_nominative_labtest_clinical_metadata_collection(self) -> Collection:
        """
        Initialises collection containing the processed nominative clinical and labtest data acquired from the ODS sftp.
        :return: Opened nominative labtest and clinical metadata collection
        """
        nominative_labtest_clinical_metadata_collection = self._open_mongo_collection(
            self.opened_mongo_database, "nominative_labtest_clinical_metadata")
        return nominative_labtest_clinical_metadata_collection

    def initialise_unprocessed_nominative_labtest_metadata_collection(self) -> Collection:
        """
        Initialises collection containing the unprocessed nominative labtest data acquired from the ODS sftp.
        :return: Opened unprocessed labtest metadata collection
        """
        unprocessed_nominative_labtest_metadata_collection = self._open_mongo_collection(
            self.opened_mongo_database, "unprocessed_nominative_labtest_metadata")
        return unprocessed_nominative_labtest_metadata_collection

    def initialise_unprocessed_nominative_clinical_metadata_collection(self) -> Collection:
        """
        Initialises collection containing the unprocessed nominative clinical data acquired from the ODS sftp.
        :return: Opened unprocessed clinical metadata collection
        """
        unprocessed_nominative_clinical_metadata_collection = self._open_mongo_collection(
            self.opened_mongo_database, "unprocessed_nominative_clinical_metadata")
        return unprocessed_nominative_clinical_metadata_collection

    def initialise_isolates_rejected_coreqc_collection(self) -> Collection:
        """
        Initialises collection containing the isolates rejected because of the core quality metrics.
        :return: Opened isolates rejected coreqc collection
        """
        isolates_rejected_coreqc_collection = self._open_mongo_collection(
            self.opened_mongo_database, "isolates_rejected_coreqc")
        return isolates_rejected_coreqc_collection
