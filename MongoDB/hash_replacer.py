import argparse
import logging
import yaml
from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern
from pathlib import Path
import sys

from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG


def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", required=True, type=str)
    parser.add_argument("--species", required=True, type=str,
                        choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    return parser.parse_args()

def query_hashes_of_scheme(hashed_AD_collection, scheme: str) -> list:
    return [document for document in hashed_AD_collection.with_options(read_concern=ReadConcern(level="majority")).find({"scheme": scheme, "resolved_AD": 0})]


if __name__ == '__main__':
    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(
        config_data, args.species)
    hashed_AD_collection = mongoinit.initialise_hashing_collection(config_data, args.species)

    # Query the docs with hashes for this particular scheme
    documents_list = query_hashes_of_scheme(hashed_AD_collection, args.scheme)
    logging.info(f"documents list: {documents_list}")
    if documents_list == []:
        pass
    else:
        locus_hash_dict = {}
        for hash_document in documents_list:
            if hash_document['locus'] in locus_hash_dict.keys():
                locus_hash_dict[hash_document['locus']] = locus_hash_dict[hash_document['locus']].append(hash_document['hashed_allele'])
            else:
                locus_hash_dict[hash_document['locus']] = [hash_document['hashed_allele']]
        for locus, hash_list in locus_hash_dict.items():
            if args.species == 'stec':
                fasta_file = Path(f"/db/sequence_typing/ecoli/{args.scheme.replace('-','_')}/{locus}/{locus.lower()}.fasta")
            else:
                fasta_file = Path(f"/db/sequence_typing/{args.species}/{args.scheme.replace('-', '_')}/{locus}/{locus.lower()}.fasta")
            import os
            if os.path.isfile(fasta_file):
                logging.info(f"opening fasta file: {fasta_file}")
            else:
                raise RuntimeError(f"Fasta file path for locus {locus} does not seem to adhere to the normal fasta path syntax")
            logging.info(f"hash list: {hash_list} for locus {locus}")
            with fasta_file.open() as handle:
                from Bio import SeqIO
                alleles = list(SeqIO.parse(handle, 'fasta'))
                for allele in alleles:
                    import hashlib
                    hashed_allele = hashlib.md5((allele.seq).encode()).hexdigest()
                    if hashed_allele in hash_list:
                        allele_id = allele.id.split('_')[-1]
                        # Update collections
                        logging.debug(f"replacing {hashed_allele} by {allele_id} for locus {locus}")
                        isolates_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                            { f"results.{args.scheme}.loci":
                                  { "$elemMatch":
                                        { "Locus": locus, "Allele": hashed_allele } } },
                            { "$set": { f"results.{args.scheme}.loci.$.Allele": allele_id } })
                        isolates_badqc_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                            { f"results.{args.scheme}.loci":
                                  { "$elemMatch":
                                        { "Locus": locus, "Allele": hashed_allele } } },
                            {"$set": {f"results.{args.scheme}.loci.$.Allele": allele_id}})
                        # todo think if old results collection should be updated aswell
                        isolateresults_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                            { f"results.{args.scheme}.loci":
                                  { "$elemMatch":
                                        { "Locus": locus, "Allele": hashed_allele } } },
                            {"$set": {f"{args.scheme}.loci.$.Allele": allele_id}})
                        # Update document but do not delete
                        hashed_AD_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                            {"scheme": args.scheme, "resolved_AD": 0, "locus": locus},
                            {"$set": {"resolved_AD": allele_id}})
