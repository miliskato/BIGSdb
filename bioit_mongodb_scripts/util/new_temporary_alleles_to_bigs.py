import datetime
import logging
import socket
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSequences
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


class NewTemporaryAllelesToBigs:
    """
    Inserts all new temporary alleles into BIGSdb, decides what is new based on a date that is stored
    in the update metadata collection. This date is updated at the successful end of this script.
    """
    def __init__(self, species: str, mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Intialises this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :return: None
        """
        self._species = species

        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_AZURE')
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()
        self._hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        # Open sequences psql table connection
        self._seqdef_sequences_psql_tbl = TblSequences(self._species)
        # Prepare for main
        self._current_update_date = datetime.datetime.utcnow()
        self._last_date_of_update = self._get_last_date_of_update()
        if self._last_date_of_update is None:
            self._last_date_of_update = datetime.datetime(1970, 1, 1)  # unix time
        self._new_sequences = self._get_new_sequence()

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
        Inserts new temporary alleles from MongoDB to BIGSdb.
        :return: None.
        """
        if len(self._new_sequences) > 0:
            self.__insert_new_alleles()
        self.__update_last_update_date()

    def _get_last_date_of_update(self) -> Optional[date]:
        """
        Retrieve in MongoDB the date of the last update.
        :return: a date in iso UTC format
        """
        query = self._update_metadata_collection.find_one({'metadata': 'last_update_temporary_alleles', 'host': socket.gethostname()})
        if not query:
            # When migrating an existing instance to this flow with separate temporary alleles, the last temporary
            # alleles update date will have been the last clustering update date (last_update)
            self._update_metadata_collection.find_one({'metadata': 'last_update', 'host': socket.gethostname()})
        return query['last_update_date'] if query else None

    def _get_new_sequence(self) -> List[Dict[str, Any]]:
        """
        Retrieve all the new hashed alleles from the mongo hashed alleles collection that have been added since the
        date of the last update.
        :return: A list of documents containing the information about the new alleles.
        """
        return list(self._hashed_ad_collection.find({'insertion_date': {'$gt': self._last_date_of_update},
                                                     'resolved_AD': 0}))

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

    def __update_last_update_date(self) -> None:
        """
        Update into Mongodb the last date of update once the update has been carried out.
        :return: None.
        """
        self._update_metadata_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {'metadata': 'last_update_temporary_alleles', 'host': socket.gethostname()},
            {"$set": {'last_update_date': self._current_update_date}}, upsert=True)

    def __exit__(self) -> None:
        """
        Closes the isolates psql table when the class is closed
        :return: None
        """
        self._seqdef_sequences_psql_tbl.close()
