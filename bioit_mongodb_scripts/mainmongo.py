#!/usr/bin/env python
import argparse
import hashlib
import json
import logging
import re
import shutil
import socket
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

# import dnspython
# somehow this package is a requirement without actually needing to be imported, probably imported in pymongo
import pymongo
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import CLUSTERING_CONFIG
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.error import *
from bioit_mongodb_scripts.util.mongo_custom_clustering import MongoCustomClustering
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email, convert_dmyhms_to_ymd


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    !! If new arguments are added, Also add arguments/variables to main function/class!!
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    mutually_exclusive_group = parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--subvaldict', type=json.loads)
    mutually_exclusive_group.add_argument('--jsonfilepath', type=Path)
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    parser.add_argument("--results_type", required=True, type=str, choices=['new_isolate', 'reanalysis', 'badqc_validated', 'resequencing_validated'])
    parser.add_argument("--reportdirectorypath", required=False, type=str)  # not mandatory because of reanalysis
    parser.add_argument("--fastafilepath", required=False, type=str)  # not mandatory because of reanalysis
    parser.add_argument("--vcffilepath", required=False, type=str)  # not mandatory because of reanalysis
    parser.add_argument("--technical_id", required=True, type=str)
    parser.add_argument('--alternate_connection_string', type=str, help=argparse.SUPPRESS)  # will replace connection string, only for small testing purposes
    parser.add_argument('--alternate_dtap', choices=['dev', 'test', 'acc', 'prod'], help=argparse.SUPPRESS)  # will replace connection string, only for small testing purposes
    parser.add_argument('--dont_send_email', action='store_true', help=argparse.SUPPRESS)  # will not send emails, mainly used for blocking the reanalysis spam
    parser.add_argument('--uploader_mail_address', required=True, type=str)
    return parser.parse_args()


class MainMongo:
    """
    Class containing definitions to insert samples into MongoDB
    """
    def __init__(self, technical_id: str, species: str, results_type: str, uploader_mail_address: str, jsonfilepath: Path = None,
                 subvaldict: Dict[str, str] = None, reportdirectorypath: Path = None, fastafilepath: Path = None,
                 vcffilepath: Path = None, alternate_connection_string: Union[bool, str] = False, alternate_dtap: Union[str, None] = None,
                 dont_send_email: bool = False, mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Intialises this class and executes the main function which will insert/update the sample in a mongodb collection containing isolates
        !! If parameters/arguments are added here, also add them to the argparse function!!
        :param technical_id: sample id/ isolates id
        :param species: commonly used bioit species name: either genus or specific like stec
        :param results_type: Any of 'new_isolate', 'reanalysis', 'badqc_validated', 'resequencing_validated'
        :param jsonfilepath: filepath of the json input file (output of pipeline)
        :param subvaldict: validation dictionary, received after validation through bigsdb (either results type badqc_validated or resequencing_validated')
        :param reportdirectorypath: absolute path to where the directory containing all files required for html are stored (only required for new_isolate)
        :param fastafilepath: absolute path to where the fasta file is stored (only required for new_isolate)
        :param vcffilepath: absolute path to where the fasta file is stored (only required for new_isolate)
        :param alternate_connection_string: use given alternate connection string, used for testing on the free Atlas Cluster
        :param alternate_dtap: alternative dtap than what is in the config file
        :param mongo_config_data: Pass provided mongo_config_data to MongoInitialisation, else get mongo_config_data from file
        :return: None
        """
        # Input parameters
        self._uploader_mail_address = uploader_mail_address
        self._technical_id = technical_id
        self._species = species
        self._results_type = results_type
        self._jsonfilepath = jsonfilepath
        self._subvaldict = subvaldict
        self._reportdirectorypath = reportdirectorypath
        self._fastafilepath = fastafilepath
        self._vcffilepath = vcffilepath
        self._alternate_connection_string = alternate_connection_string
        self._alternate_dtap = alternate_dtap
        self._dont_send_email = dont_send_email
        self._mongo_config_data = mongo_config_data  # no need to get if not provided because it is only
        # needed in mongoinit and there it can be retrieved by itself

        # Open collections
        self._mongoinit = MongoInitialisation(self._species,
                                              alternate_connection_string=self._alternate_connection_string,
                                              alternate_dtap=self._alternate_dtap,
                                              mongo_config_data=self._mongo_config_data)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, \
            self._isolates_resequencing_collection = self._mongoinit.initialise_collections()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = \
            self._mongoinit.initialise_clustering_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()

        # Open querying class instance
        self._mongoquerying = Mongoquerying()

        # Parameter compatibility checks
        self._parameter_compatibility_checks()

        # Execute main function
        try:
            self._main_mongo()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: {exceptionmessage}\n{traceback.format_exc()}")

    def _parameter_compatibility_checks(self) -> None:
        """
        Checks compatibility of argparse arguments
        :return: None
        """
        # if args.results_type == 'reanalysis' and args.bigs is True:
        #     raise Exception('Bigs upload only available for new isolates')
        if self._results_type == 'badqc_validated' and not self._subvaldict:
            raise Exception('subvaldict necessary when using results_type badqc_validated')
        if self._results_type == 'resequencing_validated' and not self._subvaldict:
            raise Exception('subvaldict necessary when using results_type badqc_validated')
        if self._results_type == 'new_isolate' and not self._jsonfilepath:
            raise Exception('jsonfilepath necessary when using results_type new_isolate')
        if self._results_type == 'reanalysis' and not self._jsonfilepath:
            raise Exception('jsonfilepath necessary when using results_type reanalysis')

        if self._results_type == 'new_isolate' and not self._reportdirectorypath:
            raise Exception('reportdirectorypath necessary when using results_type new_isolate')
        if self._results_type == 'new_isolate' and not self._fastafilepath:
            raise Exception('fastafilepath necessary when using results_type new_isolate')
        if self._results_type == 'new_isolate' and self._species == 'mycobacterium' and not self._vcffilepath:
            raise Exception('vcffilepath necessary when using results_type new_isolate')
        # the below check is already handled in mongo initialisation
        # if self._alternate_dtap and self._alternate_dtap not in ['dev', 'test', 'acc', 'prod']:
        #     raise Exception('alternate dtap needs to be a valid choice between; dev, test, acc, prod')
        # new isolates should not have vcfs necesarily if they are uploaded using only a fasta
        # if self._results_type == 'new_isolate' and not self._vcffilepath:
        #     raise Exception('vcffilepath necessary when using results_type new_isolate')

    def _main_mongo(self) -> None:
        """
        Handles a sample according to the given results_type:
        if new_isolate; check whether really new, and if not resequencing, if really new insert into either bad or good
        if reanalysis; check if really new reanalysis, if so update
        if badqc_validated; if good outcome, reinsert as new_isolate. Else update metadata
        if resequencing_validated; if good outcome, treat as reanalysis. Else update metadata
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # If statement for results_type
        if self._results_type == "new_isolate":
            with Path(self._jsonfilepath).open('r') as handle:
                new_records = json.load(handle)
            # todo check if fasta path and vcf path are real?
            isolates_findone: Dict[str, Any] = self._isolates_collection.find_one({"_id": self._technical_id})
            if isolates_findone:
                self.__new_resequencing_arrival(new_records, isolates_findone, self._isolates_collection)
            else:
                # We're excluding documents that were validated, additionally only documents that were validated with a negative result are still in the badqc collection
                # Additionally, documents that were negatively validated now have their _id removed in sample_validation_to_mongo.py
                isolates_badqc_findone = self._isolates_badqc_collection.find_one({"_id": self._technical_id, "validation": None})
                if isolates_badqc_findone:
                    # unvalidated badqc isolates are taken care of in the _new_resequencing_arrival function
                    self.__new_resequencing_arrival(new_records, isolates_badqc_findone, self._isolates_badqc_collection)
                else:
                    self.__new_isolate_wrapper(new_records)
        elif self._results_type == 'badqc_validated':
            sample_doc = self._isolates_badqc_collection.find_one({"_id": self._technical_id})
            new_records = sample_doc['results']
            self._fastafilepath = sample_doc['fasta_path']
            self._vcffilepath = sample_doc['vcf_path']
            self.__new_isolate_wrapper(new_records)
        elif self._results_type == "reanalysis" or self._results_type == 'resequencing_validated':
            try:
                current_results_document = \
                    self._mongoquerying.query_docs_by_ids(self._isolates_collection, [self._technical_id])[0]
            except Exception as exceptionmessage:
                send_email(
                    f"{exceptionmessage}\n{traceback.format_exc()}",
                    f"{Path(__file__).name} fail on host {socket.gethostname()}: This reanalysis technical id ({self._technical_id}) is not present in the isolates collections",
                    dont_send_email=self._dont_send_email)
                raise MongoMissingValueIsolateCollectionError(
                    f"{Path(__file__).name} fail on host {socket.gethostname()}: This reanalysis technical id ({self._technical_id}) is not present in the isolates collections")
            if self._results_type == "reanalysis":
                with Path(self._jsonfilepath).open('r') as handle:
                    new_results_handle = json.load(handle)
            else:  # self._results_type == 'resequencing_validated'
                new_results_handle = self._isolates_resequencing_collection.find_one({"_id": self._technical_id})

            self.__new_reanalysis_wrapper(current_results_document, new_results_handle)

    def __new_isolate_wrapper(self, new_records: Dict[str, Any]) -> None:
        """
        Handles and inserts new isolates, whether that be actual new isolates or validated bad samples
        :param new_records: results dictionary that is modified and inserted
        :return: None
        """
        new_records["isolates_id"] = self._technical_id
        good_sample_quality = True
        if self._results_type == 'new_isolate':
            try:
                for qc_type in new_records['qc']:
                    for key in new_records['qc'][qc_type]:
                        if key.endswith('status') and new_records['qc'][qc_type][key] == 'Failed':
                            #good_sample_quality = False
                            continue  # temp fix: on NRC platform, once a sample is uploaded is considered of good quality.

            except KeyError:
                send_email(
                    f"No qc values found in the given results for {self._technical_id}\n{traceback.format_exc()}",
                    dont_send_email=self._dont_send_email)
                raise KeyError('No qc values found in the given results')
        if good_sample_quality:
            new_records = self.___find_hashes_in_results_and_add_to_collection(new_records, 'new_isolate')
            new_records = self.___convert_typinghitdictionaries_to_lists(new_records)
            new_isolate_dictionary = self.___new_isolate(new_records)
            if 'cgmlst' in new_records:
                clustering_input = self._mongoquerying.singledoc_typing_results_by_technicalids_and_scheme(
                    new_isolate_dictionary, "cgmlst", self._headers_collection)
                custom_clustering = MongoCustomClustering(clustering_input[0], clustering_input[1], self._species,
                                                          mongo_config_data=self._mongo_config_data)
                logging.info(f"Running the clustering for the isolate {self._technical_id}")
                sp_thresholds = f"clustering_thresholds_{self._species}"
                cg_sequence_type = custom_clustering.run_custom_clustering(CLUSTERING_CONFIG[sp_thresholds])
                new_isolate_dictionary['results']['cgST'] = cg_sequence_type
            if self._results_type == 'badqc_validated':
                new_isolate_dictionary['validation'] = self._subvaldict
                self._isolates_badqc_collection.delete_one({'_id': new_records["isolates_id"]})
            self.___write_document(self._isolates_collection, new_isolate_dictionary)
            logging.info(f"Wrote new isolate {self._technical_id} and its result to {self._species} database")
        else:
            self.___write_document(self._isolates_badqc_collection,
                                   self.___new_isolate(new_records))
            logging.warning(
                f"New isolate {self._technical_id} failed quality control for one or more checks. It's results were written to the 'isolates_badqc' collection in the {self._species} database")

    def __new_resequencing_arrival(self, new_records: Dict[str, Union[str, object]], document_original: Dict[str, Union[str, object]],
                                   collection_in: pymongo.collection.Collection) -> None:
        """
        After an id is found in either isolates or isolates_badqc; this workflow will determine if it really is a resequencing, and if so insert it into isolates_resequencing
        :param new_records: results dictionary that is modified and inserted
        :param document_original: original document including the sample metadata and headers and results
        :param collection_in: the collection that the orignal sample was in
        :return: None
        """
        # https://git.sciensano.be/bioit/BIGSdb/src/d2a261056221056e56df6aa584563454f6bfec3a/lib/BIGSdb/SubmitPage.pm#L2800
        # 2022-12-20 Check whether resequencing; if resequencing; fasta md5sum should be different from original one. debating whether to store md5 in mongo or not
        # resequencings should be rare so we can afford multiple finds
        with Path(document_original['fasta_path']).open('r') as handle_ori, Path(self._fastafilepath).open('r') as handle_new:
            md5_original = hashlib.md5(bytes(handle_ori.read(), 'utf-8')).hexdigest()
            md5_new = hashlib.md5(bytes(handle_new.read(), 'utf-8')).hexdigest()
        if md5_original != md5_new:
            # this is an actual resequencing because the fastafilepath is different

            if collection_in == self._isolates_badqc_collection:
                send_email(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while the sample is present in the isolates_badqc collection and has not yet been validated, validate the bad qc in bigs before trying to reupload this resequencing.",
                    dont_send_email=self._dont_send_email)
                raise MongoResequencingNoIsolateError(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while the sample is present in the isolates_badqc collection and has not yet been validated, validate the bad qc in bigs before trying to reupload this resequencing.")
            previous_resequencings = list(
                self._isolates_resequencing_collection.find({'results.isolates_id': self._technical_id},
                                                            {'_id': 1, 'fasta_path': 1}))
            # new_resequencing = True
            if len(previous_resequencings) > 0:
                send_email(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing "
                    f"while one or more resequencings were already present: '{previous_resequencings}' in {self._isolates_resequencing_collection.database.name} "
                    f"on host {socket.gethostname()}, validate the original resequencing in bigs before uploading new resequencings.",
                    dont_send_email=self._dont_send_email)
                raise MongoTooManyResequencingsError(f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while one or more resequencings were already present: '{previous_resequencings}' in {self._isolates_resequencing_collection.database.name} on host {socket.gethostname()}, validate the original resequencing in bigs before uploading new resequencings.")
            else:
                new_records["isolates_id"] = self._technical_id
                new_isolate = self.___new_isolate(new_records)
                new_isolate = self.___convert_typinghitdictionaries_to_lists(new_isolate)
                self.___write_document(self._isolates_resequencing_collection, new_isolate)
        else:
            send_email(
                f"A duplicate resequencing for  {self._technical_id} was submitted to the isolates_resequencing ",
                dont_send_email=self._dont_send_email)
            raise MongoResequencingAlreadyExistsError(f"A duplicate resequencing for  {self._technical_id} was submitted to the isolates_resequencing ")

    def __new_reanalysis_wrapper(self, current_results_document: Dict[str, Any], new_results_document: Dict[str, Any]) -> None:
        """
        Wrapper function for reanalysis and resequencing validated         
        :param current_results_document: the current results document dict in the Mongo collection before applying the reanalysis
        :param new_results_document: the new results document dict, under results for reanalysis, all for resequencing
        :return: None
        """
        if self._results_type == "reanalysis":
            new_results = new_results_document
        else:  # if self._results_type == 'resequencing_validated':
            new_results = new_results_document['results']
        new_results = self.___find_hashes_in_results_and_add_to_collection(new_results,
                                                                          'reanalysis')
        new_results = self.___convert_typinghitdictionaries_to_lists(new_results)

        current_results = current_results_document['results']
        if new_results["analysis_date"] == current_results["analysis_date"]:
            send_email(f"This ({self._technical_id}) is not a reanalysis but the same results\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise MongoReanalysisDateError(
                f"{Path(__file__).name} fail on host {socket.gethostname()}: This ({self._technical_id}) is not a reanalysis but the same results")
        elif convert_dmyhms_to_ymd(new_results["analysis_date"]) < convert_dmyhms_to_ymd(
                current_results["analysis_date"]):
            send_email(f"These ({self._technical_id})results seem to be older than the current results\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise MongoReanalysisDateError(
                f"{Path(__file__).name} fail on host {socket.gethostname()}: These ({self._technical_id})results seem to be older than the current results")
        any_result_changed_new_old, unchanged_results_new_old, changed_results_new_old = \
            self.___check_if_results_changed(current_results, new_results)
        # Update new results if really a reanalysis/resequencing where at least one field changed
        if 'cgmlst' in changed_results_new_old:
            clustering_input = self._mongoquerying.singledoc_typing_results_by_technicalids_and_scheme(
                {'_id': self._technical_id, 'results': new_results},
                "cgmlst", self._headers_collection)
            custom_clustering = MongoCustomClustering(clustering_input[0], clustering_input[1],
                                                      self._species, self._mongo_config_data)
            logging.info(f"Running the clustering for the isolate {self._technical_id}")
            sp_thresholds = f"clustering_thresholds_{self._species}"
            sequence_type = custom_clustering.run_custom_clustering(CLUSTERING_CONFIG[sp_thresholds])
            new_results["cgST"] = sequence_type
        deltas_new_old = self.___nested_dict_delta(current_results, new_results)
        new_results = self.___prepend_string_dot_to_dict_keys(new_results, 'results')
        new_results["results.isolates_id"] = self._technical_id
        new_results["results.results_version"] = current_results["results_version"] + 1
        if any_result_changed_new_old is True:
            new_results["results.changed_version"] = current_results["changed_version"] + 1
            logging.info(
                f"Writing new changed results and linked to isolate {self._technical_id} in {self._species}")
        else:
            logging.info(
                f"New results are not different from current results for {self._technical_id} in {self._species}, updating analysis dates and db versions.")
        if self._results_type == 'resequencing_validated':
            new_results['validation'] = self._subvaldict
            report_dir_merging_cmd = ' '.join([
                "rsync -a",
                f"{new_results_document['report_directory']}/",
                f"{current_results_document['report_directory']}/"
            ])
            command = Command(report_dir_merging_cmd)
            # run the command
            command.run(current_results_document['report_directory'])
            logging.info(f"merging the report directories of original and resequencing for isolate '{self._technical_id}'")
            if command.returncode != 0:
                send_email(f"Could not 'git' merge dir {new_results_document['report_directory']} into dir {current_results_document['report_directory']}", dont_send_email=self._dont_send_email)
                raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: Could not 'git' merge dir {new_results_document['report_directory']} into dir {current_results_document['report_directory']}")
            else:
                # Removing the temporary working dir and the remaining files that were not kept
                shutil.rmtree(Path(new_results_document['report_directory']))
                logging.info(f"Resequecing directory {new_results_document['report_directory']} deletion for isolate '{self._technical_id}' completed")
            # Remove the isolate from the resequencing collection to allow for new resequencings
            self._isolates_resequencing_collection.delete_one({'_id': self._technical_id})
        self._isolates_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {"_id": self._technical_id}, {
                "$set": {**new_results,
                         "results.results_changed_since_last_version": any_result_changed_new_old,
                         "latest_analysis_date": convert_dmyhms_to_ymd(new_results["results.analysis_date"]),
                         "previous_latest_results_document": self.___write_document(self._old_isolateresults_collection,
                                                                                    deltas_new_old)}})
        logging.info(f"Wrote new results and linked to isolate {self._technical_id} in {self._species}")

    @staticmethod
    def ___write_document(opened_collection: pymongo.collection.Collection, json_input: Dict[str, Any]) -> str:
        """
        Write a document into a collection. if the provided document doesnt contain an _id key, then it is autogenerated
        else the would be autogenerated _id field is overwritten by the one provided
        :param opened_collection: the collection where the document needs to be saved
        :param json_input: the document to store into the collection
        :return: id of inserted document (either pre-given in json_input or auto-generated by Mongo)
        """
        collection_write = opened_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
            json_input)
        logging.debug(f"Writing {collection_write.inserted_id} in collection {opened_collection}")
        return collection_write.inserted_id

    def ___new_isolate(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialises new isolate dictionary including its results
        :param results: results dictionary to be inserted
        :return: dictionary with results under results key and metadata keys at the same level of the results key
        """
        results["results_version"] = 1  # this version always increments
        results["changed_version"] = 1  # this version only increments whenever something actually changed
        new_isolate_dict = {"_id": self._technical_id,
                            "report_directory": str(self._reportdirectorypath),
                            "vcf_path": str(self._vcffilepath),
                            "fasta_path": str(self._fastafilepath),
                            "previous_latest_results_document": None,
                            "creation_date": datetime.utcnow(),
                            "latest_analysis_date": convert_dmyhms_to_ymd(results["analysis_date"]),
                            "results": results}
        return new_isolate_dict

    @staticmethod
    def ___prepend_string_dot_to_dict_keys(input_dictionary: Dict[str, Any], prepending: str = 'results') -> Dict[str, Union[str, object]]:
        """
        This function is designed to update only results that have been reanalyzed; by using dot notation in the dicts only the relevant assays/metadata are updated upon reanalysis.
        The function can of course serve other purposes
        Dot notation documentation: https://www.mongodb.com/docs/manual/core/document/#dot-notation
        :param input_dictionary: input dictionary that needs all of its upper keys prepended with the prepending string
        :param prepending: string to prepend to dictionary keys separated by dot
        :return: dict with prepended string joined with dot
        """
        import copy
        input_dictionary_copy = copy.deepcopy(input_dictionary)
        for key in input_dictionary:
            if key == 'qc' or key == 'assembly':
                for subkey in input_dictionary[key]:
                    input_dictionary_copy['.'.join([key, subkey])] = input_dictionary_copy[key][subkey]
                input_dictionary_copy.pop(key)
        keydict = {key:'.'.join([prepending, key]) for key in input_dictionary_copy.keys()}
        return {keydict[key]: value for key, value in input_dictionary_copy.items()}

    @staticmethod
    def ___max_temp_allele_name_new_entry(hashed_ad_collection: pymongo.collection.Collection,
                                          locus: str, scheme: str) -> str:
        """
        Finds the last temporary name for a hashed allele and returns a new id for the new allele to add.
        :param hashed_ad_collection: hashed allele collection from MongoDB
        :param locus: locus name
        :param scheme: scheme name
        :return: the name for the new temporary allele.
        """
        query_max_temp_allele_name_doc = hashed_ad_collection.find_one({"scheme": scheme, "locus": locus},
                                                                       sort=[('insertion_date', -1)])
        if query_max_temp_allele_name_doc is None:
            return f'{locus}_temp_1'
        else:
            max_temp_allele_name = int(query_max_temp_allele_name_doc['temp_allele_name'].split('_')[-1])
            return f'{locus}_temp_{max_temp_allele_name + 1}'

    def ___find_hashes_in_results_and_add_to_collection(self, results: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """
        Finds hashes in json output report for multilocus sequence typing schemes and adds these hashes and alleles to a separate collection: new_allele_hashes.
        Also replace the hashes by temporary allele identifiers and purges the sequences to save space
        :param results: results dictionary
        :param mode: results_type but resequencing becomes reanalyis
        :return: results
        """
        hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        for typing_scheme in ['mlst', 'cgmlst', 'mlst_warwick', 'mlst_pasteur']:
            if typing_scheme in results:
                for locus_index, allele_info in enumerate(results[typing_scheme]['loci']):
                    # check if allele designation is md5 hash (32 char combination of letters andor numbers)
                    if re.findall(r'(?i)(?<![a-z0-9])[a-z0-9]{32}(?![a-z0-9])', allele_info['Allele']):
                        logging.info('new allele detected')
                        existing_document = hashed_ad_collection.with_options(
                            read_concern=ReadConcern(level="majority")).find_one(
                            {"scheme": typing_scheme, "locus": allele_info['Locus'],
                             "hashed_allele": allele_info['Allele']})
                        if existing_document is None:
                            temp_allele = self.___max_temp_allele_name_new_entry(hashed_ad_collection, allele_info['Locus'],
                                                                                 typing_scheme)
                            self.___write_document(hashed_ad_collection, {"scheme": typing_scheme,
                                                                         "locus": allele_info['Locus'],
                                                                         "hashed_allele": allele_info['Allele'],
                                                                         "allele_sequence": allele_info['Allele_sequence'],
                                                                         "encountered_count": 1,
                                                                         "resolved_AD": 0,
                                                                         "temp_allele_name": temp_allele,
                                                                         "insertion_date": datetime.utcnow(),
                                                                         "uploader_email": self._uploader_mail_address
                                                                          })
                            results[typing_scheme]['loci'][locus_index]['Allele'] = temp_allele  # replace the name of the allele in the results (no hash anymore)
                        else:
                            temp_allele = existing_document["temp_allele_name"]
                            already_present = False
                            if mode == 'reanalysis':
                                hash_old = existing_document["hashed_allele"]
                                if hash_old == allele_info['Allele']:
                                    already_present = True
                                    logging.info('hash/temp allele already present')
                            if mode == 'new_isolate' or (mode == 'reanalysis' and not already_present):
                                hashed_ad_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                                    {"_id": existing_document['_id']},
                                    {"$inc": {"encountered_count": 1}})
                                logging.info(f"hashed allele '{allele_info['Allele']}' encounter incremented by one")
                            if existing_document['resolved_AD'] == 0:
                                results[typing_scheme]['loci'][locus_index][
                                    'Allele'] = temp_allele  # replace the name of the allele in the results (no hash anymore)
                            else:
                                results[typing_scheme]['loci'][locus_index][
                                    'Allele'] = existing_document['resolved_AD']
                        results[typing_scheme]['loci'][locus_index].pop('Allele_sequence')
        return results

    @staticmethod
    def ___check_if_results_changed(current_results: Dict[str, Any], new_results: Dict[str, Any]) -> Tuple[bool, set, set]:
        """
        Checks if any result changed between the current mongodb results and the to be inserted new results
        :param current_results: current mongodb results
        :param new_results: to be inserted results
        :return: changed bool, unchanged assays (upper keys under results = assays),
        changed assays (upper keys under results = assays)
        """
        any_result_changed = False
        unchanged_results = set()
        changed_results = set()
        for mainkey in new_results:  # mainkey is assay or metadata
            if isinstance(new_results[mainkey], dict):
                for subkey in new_results[mainkey]:
                    if mainkey not in current_results:
                        logging.info(f"{mainkey} not in current results")
                        any_result_changed = True
                        changed_results.add(mainkey)
                    elif subkey == 'loci' or subkey == 'results' or subkey.startswith('hits'):
                        if subkey not in current_results[mainkey] or new_results[mainkey][subkey] != \
                                current_results[mainkey][subkey]:
                            logging.info(f"{mainkey}{subkey} different or not in old")
                            any_result_changed = True
                            changed_results.add(mainkey)
                if mainkey not in changed_results:
                    unchanged_results.add(mainkey)
        return any_result_changed, unchanged_results, changed_results

    def ___nested_dict_delta(self, current_results: Dict[str, Any], new_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        This function calculates the delta between the new results and the current results;
        it returns the changes needed to get from the new results to the current results.
        :param current_results: current mongodb results
        :param new_results: to be inserted results
        :return: dictionary of deltas
        """
        delta_new_old = {}
        for key, value in current_results.items():
            if key in new_results:
                if isinstance(value, dict) and isinstance(new_results[key], dict):
                    nested_delta = self.___nested_dict_delta(new_results[key], value)
                    if nested_delta:
                        delta_new_old[key] = nested_delta
                elif new_results[key] != value:
                    delta_new_old[key] = value
            else:
                continue
                # delta_new_old[key] = value  # uncommenting this would lead to keys not found in the
                # new results to be added to the delta, whereas we're going to be doing
                # differential reanalysis so there will often be assays missing
        # add the isolates id as a primary key in first iteration
        if 'isolates_id' in current_results:
            delta_new_old['isolates_id'] = current_results['isolates_id']
            delta_new_old['results_version'] = current_results['results_version']
            delta_new_old['changed_version'] = current_results['changed_version']
        return delta_new_old

    def ___convert_typinghitdictionaries_to_lists(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        This function aims to reduce the memory usage of hits' metadata by only storing the metadata once in a separate collection
        and storing the results in a list instead.
        Be wary, this method does not create a deepcopy, therefore changes are applied to the input docuemnt
        even if the return value's name is modified
        :return: The converted input document
        """
        hit_metadata: Union[None, Dict[str, Union[object, str, List[str]]]] = self._headers_collection.find_one({'type': 'hit_metadata'})
        if hit_metadata is None:
            inserted_document = self._headers_collection.insert_one({'type': 'hit_metadata'})
            hit_metadata = {'_id': inserted_document.inserted_id}
        results_to_modify = (document['results'] if 'results' in document else document)  # this is not a deepcopy so results will be modified in document as well
        for mainkey in results_to_modify:  # mainkey is assay or metadata
            if isinstance(results_to_modify[mainkey], dict):
                for subkey in results_to_modify[mainkey]:
                    if subkey == 'loci' and results_to_modify[mainkey][subkey] != [] and 'DB_cluster' not in results_to_modify[mainkey][subkey][0]:
                        # sort hit dictionary keys and pop locus for the first locus
                        hit_header_list = sorted(results_to_modify[mainkey][subkey][0].keys())
                        hit_primary_key = 'Locus'
                        hit_header_list.pop(hit_header_list.index(hit_primary_key))
                        if f"{mainkey}_{subkey}" in hit_metadata.keys():
                            # check whether first locus/results/hits corresponds to the f"{mainkey}_{subkey}"'s value which is the list of headers
                            if hit_metadata[f"{mainkey}_{subkey}"] == hit_header_list:
                                meta_hit_dictionary = {}  # dictionary that will store hits and metadata e.g. {'locus1': ['DNA', '5', '12'], 'locus2': ['DNA', '10', '14']}
                                for single_hit_dictionary in results_to_modify[mainkey][subkey]:
                                    meta_hit_dictionary[single_hit_dictionary['Locus']] = [single_hit_dictionary[metadata] for metadata in hit_header_list]
                                results_to_modify[mainkey][subkey] = meta_hit_dictionary
                            else:
                                send_email(f'Headers {hit_header_list} for typing scheme {mainkey} do not match with headers from'
                                           f' header collection {hit_metadata[f"{mainkey}_{subkey}"]} for sample {self._technical_id}',
                                           dont_send_email=self._dont_send_email)
                                raise ValueError(f'Headers for typing scheme {mainkey} do not match with headers from '
                                                 f'header collection {hit_metadata[f"{mainkey}_{subkey}"]} for sample {self._technical_id}')
                        else:
                            hit_metadata[f"{mainkey}_{subkey}"] = hit_header_list
                            self._headers_collection.update_one({"_id": hit_metadata['_id']},
                                                                {"$set": {f"{mainkey}_{subkey}": hit_header_list}})
                            meta_hit_dictionary = {}  # dictionary that will store hits and metadata e.g. {'locus1': ['DNA', '5', '12'], 'locus2': ['DNA', '10', '14']}
                            for single_hit_dictionary in results_to_modify[mainkey][subkey]:
                                meta_hit_dictionary[single_hit_dictionary['Locus']] = [single_hit_dictionary[metadata]
                                                                                       for metadata in hit_header_list]
                            results_to_modify[mainkey][subkey] = meta_hit_dictionary
        return document


if __name__ == '__main__':

    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    MainMongo(args.technical_id,
              args.species,
              args.results_type,
              args.uploader_mail_address,
              jsonfilepath=(args.jsonfilepath if args.jsonfilepath else None), 
              subvaldict=(args.subvaldict if args.subvaldict else None),
              reportdirectorypath=(args.reportdirectorypath if args.reportdirectorypath else None), 
              fastafilepath=(args.fastafilepath if args.fastafilepath else None),
              vcffilepath=(args.vcffilepath if args.vcffilepath else None), 
              alternate_connection_string=(True if args.alternate_connection_string else False),
              dont_send_email=(True if args.dont_send_email else False),
              mongo_config_data=mongo_config_data)
