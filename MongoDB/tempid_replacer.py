import argparse
import hashlib
import logging
import os
import smtplib
import socket
import sys
import traceback
from email.message import EmailMessage
from pathlib import Path

import pymongo
import yaml
from Bio import SeqIO
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.components.databaseconnection import DatabaseConnection
from MongoDB.util.mongo_initialisation import MongoInitialisation
from MongoDB.config import MONGO_CONFIG

def _send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)
    logging.info(content)

def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--scheme", required=True, type=str, help='lower case scheme as in json reports/mongodb documents')
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    parser.add_argument('--alternate_connection_string', type=str,
                        help=argparse.SUPPRESS)  # will replace connection string, only for small testing purposes
    return parser.parse_args()


def _query_hashes_of_scheme(hashed_ad_collection: pymongo.collection.Collection, scheme: str) -> list:
    """
    query unresolved hashes of a given scheme in the hashes collection
    :param hashed_ad_collection: Collection containing hashed alleles, sequences and more properties
    :param scheme: scheme that unresolved hashes should be queried from
    :return: list of documents (dicts) of unresolved hashes
    """
    return [document for document in hashed_ad_collection.with_options(read_concern=ReadConcern(level="majority")).find({"scheme": scheme, "resolved_AD": 0})]

def tempid_replacer(scheme: str, species: str, alternate_connection_string: str = None) -> None:
    """
    Main function
    See argparse function for variables and their requiredness
    :param scheme: 
    :param species: 
    :param alternate_connection_string: 
    :return: 
    """
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)
    
    # if testing purposes; replace connection string by testing connection string
    if alternate_connection_string:
        config_data['CONNECTION_STRING_BASE'] = 'mongodb+srv://mikelchtermans:YMFOH4BLF1U79dDk@hera-bioit-trial.vajezh0.mongodb.net'

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    try:
        # Open collections
        mongoinit = MongoInitialisation()
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections(
            config_data, species)
        hashed_AD_collection = mongoinit.initialise_hashing_collection(config_data, species)
        st_collection, cluster_membership_collection, cluster_merging_collection = \
            mongoinit.initialise_clustering_collections(config_data, species)
        # Query the docs with hashes for this particular scheme
        documents_list = _query_hashes_of_scheme(hashed_AD_collection, scheme)
        if documents_list == []:
            pass
        else:
            locus_hash_dict = {}
            for document_index, hash_document in enumerate(documents_list):
                if hash_document['locus'] in locus_hash_dict.keys():
                    locus_hash_dict[hash_document['locus']]['hashed_alleles'].append(hash_document['hashed_allele'])
                    locus_hash_dict[hash_document['locus']]['temp_alleles'].append(hash_document['temp_allele_name'])
                    locus_hash_dict[hash_document['locus']]['indexes'].append(document_index)
                else:
                    locus_hash_dict[hash_document['locus']] = {'hashed_alleles': [hash_document['hashed_allele']], 'indexes': [document_index], 'temp_alleles': [hash_document['temp_allele_name']]}
            for locus, values in locus_hash_dict.items():
                hash_list = values['hashed_alleles']
                temp_alleles_list = values['temp_alleles']
                if species == 'stec':
                    fasta_file = Path(f"/db/sequence_typing/ecoli/{scheme.replace('-','_')}/{locus}/{locus.lower()}.fasta")
                else:
                    fasta_file = Path(f"/db/sequence_typing/{species}/{scheme.replace('-', '_')}/{locus}/{locus.lower()}.fasta")
                if os.path.isfile(fasta_file):
                    logging.info(f"opening fasta file: {fasta_file}")
                else:
                    raise RuntimeError(f"Fasta file path for locus {locus} does not seem to adhere to the normal fasta path syntax")
                logging.info(f"hash list: {hash_list} for locus {locus}")
                with fasta_file.open() as handle:
                    alleles = list(SeqIO.parse(handle, 'fasta'))
                    for allele in alleles:
                        hashed_allele = hashlib.md5(allele.seq.encode()).hexdigest()
                        if hashed_allele in hash_list:
                            index_match = hash_list.index(hashed_allele)
                            temp_allele_name = temp_alleles_list[index_match]
                            allele_id = allele.id.split('_')[-1]
                            # Update collections
                            logging.debug(f"replacing {temp_allele_name} by {allele_id} for locus {locus}")
                            isolates_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                                {f"results.{scheme}.loci":
                                 {"$elemMatch":
                                  {"Locus": locus, "Allele": temp_allele_name}}},
                                {"$set":
                                 {f"results.{scheme}.loci.$.Allele": allele_id}})
                            isolates_badqc_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                                {f"results.{scheme}.loci":
                                 {"$elemMatch":
                                  {"Locus": locus, "Allele": temp_allele_name}}},
                                {"$set":
                                 {f"results.{scheme}.loci.$.Allele": allele_id}})
                            # todo think if old results collection should be updated aswell
                            old_isolateresults_collection.with_options(write_concern=WriteConcern(w="majority")).update_many(
                                {f"{scheme}.loci":
                                 {"$elemMatch":
                                  {"Locus": locus, "Allele": temp_allele_name}}},
                                {"$set":
                                 {f"{scheme}.loci.$.Allele": allele_id}})
                            # Update document but do not delete
                            hashed_AD_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                                {"scheme": scheme, "resolved_AD": 0, "locus": locus, "temp_allele_name": temp_allele_name},
                                {"$set": {"resolved_AD": allele_id}})
                            # add allele id to hash document to not have to requery for bigsdb if bigs host
                            # documents_list: list of all documents
                            # values['indexes']: list of indexes of the documents belonging to the list of hashed alleles in values['hashed_alleles']
                            # hash list: values['hashed_alleles'], list of the hashes for a locus
                            # documents_list[values['indexes'][hash_list.index(hashed_allele)]]: hash document
                            documents_list[
                                values['indexes']
                                [hash_list.index(hashed_allele)]
                                 ]['resolved_AD'] = allele_id
                            #replace in all the cgST the old temp allele by the new id
                            # greater than 0 is used to exclude the header document
                            all_st = st_collection.find({'cgST':{'$gt':0}})
                            for st in all_st:
                                profile = st['cgMLST'].split(',')
                                if temp_allele_name in profile:
                                    profile = [allele_id if x == temp_allele_name else x for x in profile]
                                    cgmlst = ','.join([str(i) for i in profile])
                                    st_collection.find_one_and_update({"cgST": st["cgST"]},
                                                            {"$set": {"cgMLST": cgmlst}})
            hostname = socket.gethostname()
            if 'bigs' in hostname and alternate_connection_string is None:
                (con_isolates, cur_isolates), (con_seqdef, cur_seqdef) = DatabaseConnection().connect_to_dbs_and_create_cursors(species)
                for hash_document in documents_list:
                    if hash_document['resolved_AD'] != 0:
                        sqlquery = """
                                   UPDATE allele_designations SET allele_id = %s 
                                   WHERE allele_id=%s AND locus=%s;"""
                        cur_isolates.execute(sqlquery, (hash_document['resolved_AD'], hash_document['hashed_allele'], hash_document['locus']))
                DatabaseConnection().close_connections(con_isolates, con_seqdef)
    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", config_data['mail'])
        raise Exception(
            f"{os.path.basename(__file__)} fail on host {socket.gethostname()}")

if __name__ == '__main__':
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(config_data['species'])

    # run main
    tempid_replacer(args.scheme, 
                    args.species, 
                    alternate_connection_string=(args.alternate_connection_string if args.alternate_connection_string else None))
    