#!/usr/bin/env python
import argparse
import hashlib
import logging
import socket
import sys
import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from pymongo.collection import Collection
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern


PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util_azure.connect_azure import ConnectAzure
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str, choices=specieslist, default=specieslist, nargs='+')
    parser.add_argument('--dtap', required=False, type=str, choices=['dev', 'test', 'acc', 'prod'],
                        default=['prod'], nargs='+')
    # this does allow for the same dtap multiple times but doesn't really matter, they're uniquely filtered using set()
    # anyway
    return parser.parse_args()


def wrapper_loop_dtap_and_species_and_schemes(speciess: List[str], dtaps: List[str]) -> None:
    """
    Loops over all dtaps and species to replace the temporary identifiers accordingly.
    :param speciess: commonly used bioit species name: either genus or specific like stec
    :param dtaps: dev, test, acc, or prod
    :return: None
    """
    for dtap in set(dtaps):
        for species in set(speciess):
            TempidReplacerAzure(species, dtap)


class TempidReplacerAzure:
    """
    Class containing definitions to check and replace temporary ids in MongoDB (and BIGSdb).
    """
    def __init__(self, species: str, dtap: str) -> None:
        """
        Initializes the class and executes the main function (auto-executable).
        :param species: commonly used bioit species name: either genus or specific like stec
        :param dtap: dtap to be used
        :return: None
        """
        self._species = species
        self._dtap = dtap

        # Connect to keyvault
        self._connection_azure = ConnectAzure(self._dtap)

        # Open collections
        self._mongoinit = MongoInitialisation(self._species,
                                              selected_connection_string='CONNECTION_STRING_AZURE',
                                              alternate_dtap=self._dtap)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_warningqc_collection, \
            self._isolates_resequencing_collection, self._isolates_goodqc_collection = \
            self._mongoinit.initialise_collections()
        self._hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = self._mongoinit.initialise_clustering_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()

        self._mongo_config_data = get_mongodb_config_data()

        # Execute main
        try:
            for scheme in self._mongo_config_data['schemes_sequence_typing']:
                self._scheme = scheme
                # Query all unresolved hashes from hash collection for this particular scheme
                documents_list = self.__query_hashes_of_scheme()
                self._tempid_replacer(documents_list)
            self._update_dbupdate_date()
        except Exception as exception_message:
            exception_subject = f"{Path(__file__).name} fail on host {socket.gethostname()} for scheme {self._scheme}"
            raise Exception(exception_subject + ' ' + str(exception_message))

    def _tempid_replacer(self, documents_list: List[Dict[str, Any]]) -> None:
        """
        Main function
        Checks the databases to see if previously defined temporary id's have been taken up in the source database.
        If so, replaces the temporary identifiers with the new source database identifier in MongoDB. If the host is a
        bigsdb host, also replace the temporary identifiers in the database, however, the current implementation will
        only replace temp identifiers if they're replaced in the current run, therefore if the script is run on another
        host first and then here, those identifiers will not be replaced in bigs. The idea is to run this script after
        a database update in order for the reanalysis to not think that an allele has changed.
        :param documents_list: list of documents (dicts) of unresolved hashes
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        if len(documents_list) != 0:
            locus_hash_dict = self.__create_locus_hash_dict(documents_list)
            for locus, values in locus_hash_dict.items():
                hash_list = values['hashed_alleles']
                fasta_file = self.__check_and_return_fasta_file(locus)
                logging.info(f"hash list: {hash_list} for locus {locus}")
                with fasta_file.open() as handle:
                    alleles = SeqIO.parse(handle, 'fasta')
                    allele: Union[SeqRecord, Any]
                    for allele in alleles:
                        hashed_allele = hashlib.md5(bytes(str(allele.seq), 'utf-8')).hexdigest()
                        if hashed_allele in hash_list:
                            self.__update_temp_to_real_mongodb(locus, allele, hashed_allele, hash_list, values, documents_list)

    def __query_hashes_of_scheme(self) -> List[Dict[str, Any]]:
        """
        Query unresolved hashes of a given scheme in the hashes collection.
        :return: list of documents (dicts) of unresolved hashes
        """
        return [document for document in
                self._hashed_ad_collection.with_options(read_concern=ReadConcern(level="majority")).find(
                    {"scheme": self._scheme, "resolved_AD": 0})]

    @staticmethod
    def __create_locus_hash_dict(documents_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
        """
        Creates a dictionary with as keys the loci and as values dictionaries where the dictioniaries' keys are
        properties concerning the alleles that have not been found in the reference database yet. More specifically:
        hashed_alleles is a list of all the hashed alleles (md5), temp_alleles is a list of all the temporary allele
        names defined by us, which are a nicer representation than a hash, indices are the indices of the respective
        alleles in the queried _documents_list
        :param documents_list: list of documents (dicts) of unresolved hashes
        :return: Dictionary containing properties concerning new alleles.
        """
        locus_hash_dict = {}
        for document_index, hash_document in enumerate(documents_list):
            if hash_document['locus'] in locus_hash_dict:
                locus_hash_dict[hash_document['locus']]['hashed_alleles'].append(hash_document['hashed_allele'])
                locus_hash_dict[hash_document['locus']]['temp_alleles'].append(hash_document['temp_allele_name'])
                locus_hash_dict[hash_document['locus']]['indices'].append(document_index)
            else:
                locus_hash_dict[hash_document['locus']] = {'hashed_alleles': [hash_document['hashed_allele']],
                                                           'indices': [document_index],
                                                           'temp_alleles': [hash_document['temp_allele_name']]}
        return locus_hash_dict

    def __check_and_return_fasta_file(self, locus: str) -> Path:
        """
        Checks if fasta file exists and returns the path if so.
        :param locus: current locus name
        :return: fasta file pathlib Path instance
        """
        if self._species == 'stec':
            fasta_file = Path(
                f"/db/sequence_typing/ecoli/{self._scheme.replace('-', '_')}/{locus}/{locus}.fasta")
        else:
            fasta_file = Path(
                f"/db/sequence_typing/{self._species}/{self._scheme.replace('-', '_')}/{locus}/{locus}.fasta")
        if fasta_file.is_file():
            logging.info(f"opening fasta file: {fasta_file}")
        else:
            raise RuntimeError(f"Fasta file path for locus {locus} of species {self._species} "
                               f"does not seem to adhere to the normal fasta path syntax")
        return fasta_file

    def __update_temp_to_real_mongodb(self, locus: str, allele: SeqRecord, hashed_allele: str, hash_list: List[str], values: Dict[str, List[Union[str, int]]], documents_list: List[Dict[str, Any]]) -> None:
        """
        Updates the temporary identifiers that are now newly in the source database to the source database's identifier
        in MongoDB. The cgmlst profiles that contain the temporary allele identifier are also updated at the same time.
        :param locus: current locus name
        :param allele: allele SeqRecord instance
        :param hashed_allele: md5 hash of the allele string
        :param hash_list: list of the hashed alleles corresponding with the indices list
        :param values: lists of hashed alleles, indices, and temp_alleles for a locus
        :param documents_list: list of documents (dicts) of unresolved hashes
        :return: None
        """
        index_match = hash_list.index(hashed_allele)
        temp_alleles_list = values['temp_alleles']
        temp_allele_name = temp_alleles_list[index_match]
        new_allele_id = allele.id.split('_')[-1]
        # Get allele index in
        hit_metadata = self._headers_collection.find_one({'type': 'hit_metadata'})
        allele_index = hit_metadata[f"{self._scheme}_loci"].index('Allele')
        # Update collections
        logging.debug(f"replacing {temp_allele_name} by {new_allele_id} for locus {locus}")
        self.___update_temp_allele_to_new(self._isolates_collection, locus, temp_allele_name, new_allele_id, allele_index)
        self.___update_temp_allele_to_new(self._isolates_warningqc_collection, locus, temp_allele_name, new_allele_id)
        self.___update_temp_allele_to_new(self._isolates_resequencing_collection, locus, temp_allele_name, new_allele_id)
        self.___update_temp_allele_to_new(self._old_isolateresults_collection, locus, temp_allele_name, new_allele_id, allele_index, in_results=False)
        self.___update_temp_allele_to_new(self._isolates_goodqc_collection, locus, temp_allele_name, new_allele_id)
        # Update document but do not delete
        self._hashed_ad_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {"scheme": self._scheme, "resolved_AD": 0, "locus": locus, "temp_allele_name": temp_allele_name},
            {"$set": {"resolved_AD": new_allele_id}})
        # add allele id to hash document to not have to requery for bigsdb if bigs host
        # documents_list: list of all documents
        # values['indices']: list of indices of the documents belonging to the list of hashed alleles in values['hashed_alleles']
        # hash list: values['hashed_alleles'], list of the hashes for a locus
        # documents_list[values['indices'][hash_list.index(hashed_allele)]]: hash document
        hashed_allele_index_in_doclist = int(values['indices'][hash_list.index(hashed_allele)])
        documents_list[hashed_allele_index_in_doclist]['resolved_AD'] = new_allele_id
        # replace in all the cgST the old temp allele by the new id
        # use the power of list to replace only where it's needed
        if self._scheme == 'cgmlst':
            headers_cgmlst = self._headers_collection.find_one({'type': 'cgmlst_headers'})['headers']
            locus_index = headers_cgmlst.index(locus)
            self._st_collection.update_many(
                {f"cgMLST.{locus_index}": temp_allele_name},
                update={"$set": {f"cgMLST.{locus_index}": int(new_allele_id)}}
            )
            logging.debug(f'[information_temp_id_replacer] Locus {locus} at position {locus_index} is replacing {temp_allele_name} by {new_allele_id}')

    def ___update_temp_allele_to_new(self, collection: Collection, locus: str, temp_allele_name: str,
                                     new_allele_id: str, allele_index: int = None, in_results: bool = True) -> None:
        """
        Updates the collections containing isolates with the newly found alleles that were previously temporary
        identifiers.
        :param collection: collection containing isolates that needs to be updated
        :param locus: locus name
        :param temp_allele_name: temporary identifier name
        :param new_allele_id: new source allele id
        :param allele_index: index of the allele in the new hit metadata list
        :param in_results: are the assays located under results or not? usually yes except for old_isolate_results
        :return: None
        """
        # the commented code below is cleaner than the one not commented, but for some
        # reason the operator $index was not found, 'unknown operator: $index', this is maybe due to
        # the mongodb version being too low but atlas is supposedly 5.0 and pymongo4.2.0 is supposed
        # to support mongodb 5.0
        # collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
        #     {f"{'results.' if in_results else ''}{self._scheme}.loci.{locus}":
        #      {"$elemMatch": {"$eq": temp_allele_name, "$index": allele_index}}},
        #     {"$set":
        #      {f"{'results.' if in_results else ''}{self._scheme}.loci.{locus}.{allele_index}": new_allele_id}})
        if allele_index:  # new way of storing typing results
            collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                {f"{'results.' if in_results else ''}{self._scheme}.loci.{locus}.{allele_index}": temp_allele_name},
                {"$set":
                 {f"{'results.' if in_results else ''}{self._scheme}.loci.{locus}.{allele_index}": new_allele_id}})
        else:
            collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                {f"{self._scheme}.loci":
                 {"$elemMatch":
                  {"Locus": locus, "Allele": temp_allele_name}}},
                {"$set":
                 {f"{self._scheme}.loci.$.Allele": new_allele_id}})

    def _update_dbupdate_date(self) -> None:
        """
        Updates the last dbupdate date in the update metadata collection of MongoDB.
        :return: None
        """
        self._update_metadata_collection.update_one(
            {'metadata': 'last_dbupdate_date'},
            {'$set': {
                'last_update_date': datetime.datetime.now(datetime.timezone.utc)}
             },
            upsert=True
        )


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    wrapper_loop_dtap_and_species_and_schemes(args.species, args.dtap)
