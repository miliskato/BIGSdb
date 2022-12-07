import argparse
import logging
import yaml
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
from pathlib import Path
import sys
import socket
from Bio import SeqIO
import os
import hashlib


PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import Database_connection
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG


def _parse_arguments(specieslist) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", required=True, type=str, help='lower case scheme as in json reports/mongodb documents')
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    return parser.parse_args()


def query_hashes_of_scheme(hashed_ad_collection: object, scheme: str) -> list:
    """
    query unresolved hashes of a given scheme in the hashes collection
    :param hashed_ad_collection: Collection containing hashed alleles, sequences and more properties
    :param scheme: scheme that unresolved hashes should be queried from
    :return: list of documents (dicts) of unresolved hashes
    """
    return [document for document in hashed_ad_collection.with_options(read_concern=ReadConcern(level="majority")).find({"scheme": scheme, "resolved_AD": 0})]


if __name__ == '__main__':
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(config_data['species'])

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit.initialise_collections(
        config_data, args.species)
    hashed_AD_collection = mongoinit.initialise_hashing_collection(config_data, args.species)
    st_collection, cluster_membership_collection = \
        mongoinit.initialise_clustering_collections(config_data, args.species)
    # Query the docs with hashes for this particular scheme
    documents_list = query_hashes_of_scheme(hashed_AD_collection, args.scheme)
    if documents_list == []:
        pass
    else:
        locus_hash_dict = {}
        for document_index, hash_document in enumerate(documents_list):
        locus_tm_name_dict = {}
        for hash_document in documents_list:
            if hash_document['locus'] in locus_hash_dict.keys():
                locus_hash_dict[hash_document['locus']['alleles']].append(hash_document['hashed_allele'])
                locus_hash_dict[hash_document['locus']['indexes']].append(document_index)
                #if multiple alleles for one locus
                locus_hash_dict[hash_document['locus']].append(hash_document['hashed_allele'])
                locus_tm_name_dict[hash_document['locus']].append(hash_document['allele_number'])
            else:
                locus_hash_dict[hash_document['locus']] = {'alleles': [hash_document['hashed_allele']], 'indexes': [document_index]}
        for locus, values in locus_hash_dict.items():
            hash_list = values['alleles']
                locus_hash_dict[hash_document['locus']] = [hash_document['hashed_allele']]
                locus_tm_name_dict[hash_document['locus']] = [hash_document['allele_number']]
        for locus, hash_list in locus_hash_dict.items():
            locus_tm_names = locus_tm_name_dict[locus]
            if args.species == 'stec':
                fasta_file = Path(f"/db/sequence_typing/ecoli/{args.scheme.replace('-','_')}/{locus}/{locus.lower()}.fasta")
            else:
                fasta_file = Path(f"/db/sequence_typing/{args.species}/{args.scheme.replace('-', '_')}/{locus}/{locus.lower()}.fasta")
            if os.path.isfile(fasta_file):
                logging.info(f"opening fasta file: {fasta_file}")
            else:
                raise RuntimeError(f"Fasta file path for locus {locus} does not seem to adhere to the normal fasta path syntax")
            logging.info(f"hash list: {hash_list} for locus {locus}")
            with fasta_file.open() as handle:
                alleles = list(SeqIO.parse(handle, 'fasta'))
                for allele in alleles:
                    hashed_allele = hashlib.md5(allele.seq.encode()).hexdigest()
                    hashed_allele = hashlib.md5((allele.seq).encode()).hexdigest()
                    if hashed_allele in hash_list:
                        index_match = hash_list.index(hashed_allele)
                        name_allele = locus_tm_names[index_match]
                        allele_id = allele.id.split('_')[-1]
                        # Update collections
                        logging.debug(f"replacing {hashed_allele} by {allele_id} for locus {locus}")
                        isolates_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                            {f"results.{args.scheme}.loci":
                             {"$elemMatch":
                              {"Locus": locus, "Allele": hashed_allele}}},
                            {"$set":
                             {f"results.{args.scheme}.loci.$.Allele": allele_id}})
                        isolates_badqc_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                            {f"results.{args.scheme}.loci":
                             {"$elemMatch":
                              {"Locus": locus, "Allele": hashed_allele}}},
                            {"$set":
                             {f"results.{args.scheme}.loci.$.Allele": allele_id}})
                        # todo think if old results collection should be updated aswell
                        isolateresults_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                            {f"{args.scheme}.loci":
                             {"$elemMatch":
                              {"Locus": locus, "Allele": hashed_allele}}},
                            {"$set":
                             {f"{args.scheme}.loci.$.Allele": allele_id}})
                        # Update document but do not delete
                        hashed_AD_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                            {"scheme": args.scheme, "resolved_AD": 0, "locus": locus},
                            {"$set": {"resolved_AD": allele_id}})
                        # add allele id to hash document to not have to requery for bigsdb if bigs host
                        # documents_list: list of all documents
                        # values['indexes']: list of indexes of the documents belonging to the list of hashed alleles in values['alleles']
                        # hash list: values['alleles'], list of the hashes for a locus
                        # documents_list[values['indexes'][hash_list.index(hashed_allele)]]: hash document
                        documents_list[
                            values['indexes']
                            [hash_list.index(hashed_allele)]
                             ]['resolved_AD'] = allele_id
                        #replace in all the cgST the old temp allele by the new id
                        all_st = st_collection.find({'ST':{'$gt':0}})
                        for st in all_st:
                            profile = st['cgMLST'].split(',')
                            if name_allele in profile:
                                profile = [allele_id if x == name_allele else x for x in profile]
                                cgmlst = ','.join([str(i) for i in profile])
                                st_collection.find_one_and_update({"ST": st["ST"]},
                                                        {"$set": {"cgMLST": cgmlst}})
        hostname = socket.gethostname()
        if 'bigs' in hostname:
            cur_isolates, cur_seqdef = Database_connection().open_database_connections(args.species)
            for hash_document in documents_list:
                if hash_document['resolved_AD'] != 0:
                    cur_isolates.execute(f"UPDATE allele_designations SET allele_id='{hash_document['resolved_AD']}' WHERE allele_id='{hash_document['hashed_allele']}' AND locus='{hash_document['locus']}'")
