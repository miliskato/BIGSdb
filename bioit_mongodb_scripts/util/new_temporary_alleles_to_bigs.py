import datetime
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

from pymongo.write_concern import WriteConcern


PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSequences
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import send_email


class NewTemporaryAllelesToBigs:
    """
    Inserts all new temporary alleles into BIGSdb, decides what is new based on a date that is stored
    in the update metadata collection. This date is updated at the successful end of this script.
    """

    def __init__(self, species: str, mongo_config_provider: MongoConfigProvider) -> None:
        """
        Intialises this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like enterococcus_faecalis
        :param mongo_config_provider: the mongodb configuration provider
        :return: None
        """
        self._species = species

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_provider.get_azure_connection_string(species), mongo_config_provider.dtap)
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()
        self._hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        # Prepare for main
        self._current_update_date = datetime.datetime.now(datetime.timezone.utc)
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
            self.__update_sequences_insertion_status_in_bigsdb()
        self.__update_last_update_date()

    def _get_new_sequence(self) -> List[Dict[str, Any]]:
        """
        Retrieve all the new hashed alleles from the mongo hashed alleles collection that have been added since the
        date of the last update.
        :return: A list of documents containing the information about the new alleles.
        """
        return list(self._hashed_ad_collection.find({'bigsdb_status': 'pending',
                                                     'resolved_AD': 0}))

    def __insert_new_alleles(self) -> None:
        """
        Insert into BIGSdb the new alleles retrieved during the initialization.
        :return: None.
        """
        ordered_by_locus_dict = self.___order_sequences_by_locus()
        with TblSequences(self._species) as seqdef_sequences_psql_tbl:
            for locus in ordered_by_locus_dict:
                # fetch all alleles ids already in bigs
                set_alleleid = set(item[0] for item in seqdef_sequences_psql_tbl.select_allele_from_locus((locus,)))
                for new_allele in ordered_by_locus_dict[locus]:
                    if new_allele['temp_allele_name'] not in set_alleleid:
                        seqdef_sequences_psql_tbl.insert_sequence((locus, new_allele['temp_allele_name'],
                                                                   new_allele['allele_sequence']))
                        logging.info(f"id {new_allele['temp_allele_name']} inserted into locus {locus}")

    def __update_sequences_insertion_status_in_bigsdb(self) -> None:
        """
        Turn field "bigsdb_status" to "inserted" for each doc listed in self._new_sequences
        :return: None
        """
        list_doc_id = [x.get('_id') for x in self._new_sequences]
        self._hashed_ad_collection.update_many(
            {'_id': {'$in': list_doc_id}}, {'$set': {'bigsdb_status': 'inserted'}})

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
