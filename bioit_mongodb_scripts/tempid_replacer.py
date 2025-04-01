#!/usr/bin/env python
import argparse
import hashlib
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Union

from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from pymongo.collection import Collection
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblAlleleDesignations
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", required=True, type=str, help='lower case scheme as in json reports/mongodb documents')
    parser.add_argument("--species", required=True, type=str, choices=specieslist)
    parser.add_argument("--connection_string", required=True, type=str, help='connection string variable from the config file')

    return parser.parse_args()


class TempidReplacer:
    """
    Class containing definitions to check and replace temporary ids in MongoDB (and BIGSdb)
    """

    def __init__(self, scheme: str, species: str, connection_string: str, alternate_dtap: Union[str, None] = None):
        """
        Initalizes the class and executes the main function (auto-executable)
        :param scheme: scheme that unresolved hashes should be queried from
        :param species: commonly used bioit species name: either genus or specific like stec
        :param connection_string: connection string variable from the config file
        :param alternate_dtap: alternative dtap than what is in the config file
        :return: None
        """
        self._scheme = scheme
        self._species = species
        self._connection_string = connection_string
        self._alternate_dtap = alternate_dtap

        # parse config data
        self._mongo_config_data = get_mongodb_config_data()
        # Open collections
        self._mongoinit = MongoInitialisation(self._species,
                                              selected_connection_string=self._connection_string,
                                              alternate_dtap=self._alternate_dtap,
                                              mongo_config_data=self._mongo_config_data)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, self._isolates_resequencing_collection = self._mongoinit.initialise_collections()
        self._hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = self._mongoinit.initialise_clustering_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()

        # Query all unresolved hashes from hash collection for this particular scheme
        self._documents_list = self.__query_hashes_of_scheme()

        # Execute main
        try:
            self._tempid_replacer()
        except Exception as exceptionmessage:
            exception_subject = f"{Path(__file__).name} fail on host {socket.gethostname()} for scheme {self._scheme}"
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", subject=exception_subject)
            raise Exception(exception_subject)

    def _tempid_replacer(self) -> None:
        """
        Main function
        Checks the databases to see if previously defined temporary id's have been taken up in the source database.
        If so, replaces the temporary identifiers with the new source database identifier in MongoDB
        If the host is a bigsdb host, also replace the temporary identifiers in the database, however
        the current implementation will only replace temp identifiers if theyre replaced in the current run, therefore
        if the script is run on another host first and then here, those identifiers will not be replaced in bigs.
        The idea is to run this script after a database update in order for the reanalysis to not think that an allele has changed
        :return: None
        """

        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        if len(self._documents_list) != 0:
            locus_hash_dict = self.__create_locus_hash_dict()
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
                            self.__update_temp_to_real_mongodb(locus, allele, hashed_allele, hash_list, values)
            if ('bigs' in socket.gethostname() or 'nrc' in socket.gethostname()) and self._connection_string is not 'CONNECTION_STRING_ALTERNATE':
                with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl:
                    for hash_document in self._documents_list:
                        if hash_document['resolved_AD'] != 0:
                            isolates_ad_psql_tbl.update_designations(
                                (hash_document['resolved_AD'], hash_document['locus'], hash_document['hashed_allele']))

    def __query_hashes_of_scheme(self) -> List[Dict[str, Any]]:
        """
        Query unresolved hashes of a given scheme in the hashes collection
        :return: list of documents (dicts) of unresolved hashes
        """
        return [document for document in
                self._hashed_ad_collection.with_options(read_concern=ReadConcern(level="majority")).find(
                    {"scheme": self._scheme, "resolved_AD": 0})]

    def __create_locus_hash_dict(self) -> Dict[str, Dict[str, List[str]]]:
        """
        Creates a dictionary with as keys the loci and as values dictionaries where the dictioniaries' keys are
        properties concerning the alleles that have not been found in the reference database yet. More specifically:
        hashed_alleles is a list of all the hashed alleles (md5)
        temp_alleles is a list of all the temporary allele names defined by us, which are a nicer representation than a hash
        indices are the indices of the respective alleles in the queried _documents_list
        :return: Dictionary containing properties concerning new alleles.
        """
        locus_hash_dict = {}
        for document_index, hash_document in enumerate(self._documents_list):
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
        Checks if fasta file exists and returns the path if so
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
            send_email(f"Fasta file path for locus {locus} of species {self._species} "
                       f"does not seem to adhere to the normal fasta path syntax")
            raise RuntimeError(f"Fasta file path for locus {locus} of species {self._species} "
                               f"does not seem to adhere to the normal fasta path syntax")
        return fasta_file

    def __update_temp_to_real_mongodb(self, locus: str, allele: SeqRecord, hashed_allele: str, hash_list: List[str],
                                      values: Dict[str, List[Union[str, int]]]) -> None:
        """
        Updates the temporary identifiers that are now newly in the source database to the source database's identifier in MongoDB.
        The cgmlst profiles that contains the temporary allele identifier are also updated at the same time.
        :param locus: current locus name
        :param allele: allele SeqRecord instance
        :param hashed_allele: md5 hash of the allele string
        :param hash_list: list of the hashed alleles corresponding with the indices list
        :param values: lists of hashed alleles, indices, and temp_alleles for a locus
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
        self.___update_temp_allele_to_new(self._isolates_collection, locus, temp_allele_name, new_allele_id,
                                          allele_index)
        self.___update_temp_allele_to_new(self._isolates_badqc_collection, locus, temp_allele_name, new_allele_id)
        self.___update_temp_allele_to_new(self._isolates_resequencing_collection, locus, temp_allele_name,
                                          new_allele_id)
        self.___update_temp_allele_to_new(self._old_isolateresults_collection, locus, temp_allele_name, new_allele_id,
                                          allele_index, in_results=False)
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
        self._documents_list[hashed_allele_index_in_doclist]['resolved_AD'] = new_allele_id
        # replace in all the cgST the old temp allele by the new id
        # use the power of list to replace only where it's needed
        if self._scheme == 'cgmlst':
            headers_cgmlst = self._headers_collection.find_one({'type': 'cgmlst_headers'})['headers']
            locus_index = headers_cgmlst.index(locus)
            self._st_collection.update_many(
                {f"cgMLST.{locus_index}": temp_allele_name},
                update={"$set": {f"cgMLST.{locus_index}": int(new_allele_id)}}
            )
            logging.debug(
                f'[information_temp_id_replacer] Locus {locus} at position {locus_index} is replacing {temp_allele_name} by {new_allele_id}')

    def ___update_temp_allele_to_new(self, collection: Collection, locus: str, temp_allele_name: str,
                                     new_allele_id: str, allele_index: int = None, in_results: bool = True) -> None:
        """
        Updates the collections containing isolates with the newly found alleles that were previously temporary identifiers
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
                {"$set": {f"{'results.' if in_results else ''}{self._scheme}.loci.{locus}.{allele_index}": new_allele_id}})
        else:
            collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                {f"{self._scheme}.loci": {"$elemMatch": {"Locus": locus, "Allele": temp_allele_name}}}, {"$set": {f"{self._scheme}.loci.$.Allele": new_allele_id}})


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    TempidReplacer(args.scheme, args.species, connection_string=args.connection_string)
