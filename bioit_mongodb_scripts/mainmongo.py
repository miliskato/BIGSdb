#!/usr/bin/env python
import argparse
import hashlib
import json
import logging
import socket
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

# import dnspython
# somehow this package is a requirement without actually needing to be imported, probably imported in pymongo
import yaml
from pymongo.collection import Collection
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_nrc_integration.python.config import CODES_GENOMIC_ODS
from bioit_mongodb_scripts.model.json_model import JsonReportDict, MongoRecordDict
from bioit_mongodb_scripts.util_azure.azure_service_bus_specific_messages import AzureServiceBusMessage
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util.error import *
from bioit_mongodb_scripts.util.check_coreqc_metrics import CheckCoreQCMetrics
from bioit_mongodb_scripts.util.get_coreqc_metrics import GetCoreQCMetrics
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_custom_clustering import MongoCustomClustering
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_insertion import insert_document_into_rejected_collection
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.python_utility_functions import access_value_in_dict_using_list_as_dictpath, convert_dmyhms_to_ymd, send_email
from bioit_mongodb_scripts.util.mongo_clustering_config_provider import MongoClusteringConfigProvider

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    mutually_exclusive_group = parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--subvaldict', type=json.loads)
    mutually_exclusive_group.add_argument('--jsonfilepath', type=Path)
    parser.add_argument("--species", required=True, type=str, choices=MongoConfigProvider.get_currently_supported_species())
    parser.add_argument("--results_type", required=True, type=str, choices=['new_isolate', 'reanalysis', 'goodqc_validated', 'warningqc_validated', 'resequencing_validated'])
    parser.add_argument("--reportdirectorypath", required=False, type=str)  # not mandatory because of reanalysis
    parser.add_argument("--fastafilepath", required=False, type=str)  # not mandatory because of reanalysis
    parser.add_argument("--vcffilepath", required=False, type=str)  # not mandatory because of reanalysis
    parser.add_argument("--vcffilepath_unfiltered", required=False, type=str)  # not mandatory because of reanalysis
    parser.add_argument("--original_input_format", required=False, type=str, choices=['fastq', 'fasta'])
    parser.add_argument("--technical_id", required=True, type=str)
    parser.add_argument("--technical_metadata_path", required=False, type=Path)  # not mandatory because of reanalysis
    parser.add_argument("--pipeline_hash", required=True, type=str)  # Required for DCD NRC->ODS
    parser.add_argument('--connection_string', required=False, type=str)  # will replace connection string, only for small testing purposes
    parser.add_argument('--alternate_dtap', choices=['dev', 'test', 'acc', 'prod'], help=argparse.SUPPRESS)  # will replace connection string, only for small testing purposes
    parser.add_argument('--dont_send_email', action='store_true', help=argparse.SUPPRESS)  # will not send emails, mainly used for blocking the reanalysis spam
    parser.add_argument('--disable_asb_and_clustering_for_testing', action='store_true', help=argparse.SUPPRESS)
    return parser.parse_args()


class MainMongo:
    """
    Class containing definitions to insert samples into MongoDB
    """

    def __init__(self, technical_id: str, species: str, results_type: str, pipeline_hash: str = None, jsonfilepath: Path = None,
                 subvaldict: Dict[str, str] = None, technical_metadata_path: Path = None, reportdirectorypath: Path = None, fastafilepath: Path = None,
                 vcffilepath: Path = None, vcffilepath_unfiltered: Path = None, original_input_format: Optional[Literal['fastq', 'fasta']] = None,
                 connection_string: str = None, alternate_dtap: Union[str, None] = None, dont_send_email: bool = False,
                 disable_asb_and_clustering_for_testing: bool = False) -> None:
        """
        Initialises this class and executes the main function which will insert/update the sample in a mongodb collection containing isolates
        !! If parameters/arguments are added here, also add them to the argparse function!!
        :param technical_id: sample id/ isolates id
        :param species: commonly used bioit species name: either genus or specific like stec
        :param results_type: Any of 'new_isolate', 'reanalysis', 'goodqc_validated', 'warningqc_validated', 'resequencing_validated'
        :param pipeline_hash: 10 first characters of the git hash of the pipeline used can be optional in case of validation
        :param technical_metadata_path: filepath of the json metadata file
        :param jsonfilepath: filepath of the json input file (output of pipeline)
        :param subvaldict: validation dictionary, received after validation through bigsdb (either results type goodqc_validated, warningqc_validated or resequencing_validated')
        :param reportdirectorypath: absolute path to where the directory containing all files required for html are stored (only required for new_isolate)
        :param fastafilepath: absolute path to where the fasta file is stored (only required for new_isolate)
        :param vcffilepath: absolute path to where the filtered VCF file is stored (only required for new_isolate)
        :param vcffilepath_unfiltered: absolute path to where the unfiltered VCF file is stored (only required for new_isolate)
        :param original_input_format: original input that was given to run the first analysis
        :param connection_string: connection string variable from the config file
        :param alternate_dtap: alternative dtap than what is in the config file
        :param disable_asb_and_clustering_for_testing: In order to test the reanalysis in the NRC integration, the asb
        and clustering need to be disabled to not interfere with other samples and to not interact with NRC VM. This can
        also be used to test MongoDB insertion in Azure for environments that are already accessible by end-users.
        :return: None
        """
        # Input parameters
        self._technical_id = technical_id
        self._species = species
        self._pipeline_hash = pipeline_hash
        self._results_type = results_type
        self._technical_metadata_path = technical_metadata_path
        self._jsonfilepath = jsonfilepath
        self._subvaldict = subvaldict
        self._reportdirectorypath = reportdirectorypath
        self._fastafilepath = fastafilepath
        self._vcffilepath = vcffilepath
        self._vcffilepath_unfiltered = vcffilepath_unfiltered
        self._original_input_format = original_input_format
        self._connection_string = connection_string
        self._alternate_dtap = alternate_dtap
        self._dont_send_email = dont_send_email
        self._mongo_config_provider = MongoConfigProvider(alternate_dtap)
        self._disable_asb_and_clustering_for_testing = disable_asb_and_clustering_for_testing

        self._naive_clustering_distance_matrix_file = Path(self._mongo_config_provider.get_naive_clustering_distance_matrix_file(self._species))

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, self._connection_string, self._mongo_config_provider.dtap)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_warningqc_collection, \
            self._isolates_resequencing_collection, self._isolates_goodqc_collection \
            = self._mongoinit.initialise_collections()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = \
            self._mongoinit.initialise_clustering_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()

        # Open querying class instance
        self._mongoquerying = Mongoquerying()

        # Create AzureServiceBus instance
        if not self._disable_asb_and_clustering_for_testing:
            self._asb_instance = AzureServiceBus(self._mongo_config_provider, self._species)

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
        if self._results_type == 'goodqc_validated' and not self._subvaldict:
            raise Exception('subvaldict necessary when using results_type goodqc_validated')
        if self._results_type == 'warningqc_validated' and not self._subvaldict:
            raise Exception('subvaldict necessary when using results_type warningqc_validated')
        if self._results_type == 'resequencing_validated' and not self._subvaldict:
            raise Exception('subvaldict necessary when using results_type resequencing_validated')
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
        if self._results_type == 'new_isolate' and not self._technical_metadata_path:
            raise Exception('technical metadata path necessary when using results_type new_isolate')
        if self._results_type not in ['goodqc_validated', 'warningqc_validated', 'resequencing_validation'] and not self._pipeline_hash:
            raise Exception('pipeline_hash not provided although mandatory for this result_type')

        # the below check is already handled in mongo initialisation
        # if self._alternate_dtap and self._alternate_dtap not in ['dev', 'test', 'acc', 'prod']:
        #     raise Exception('alternate dtap needs to be a valid choice between; dev, test, acc, prod')
        # new isolates should not have vcfs necessarily if they are uploaded using only a fasta
        # if self._results_type == 'new_isolate' and not self._vcffilepath:
        #     raise Exception('vcffilepath necessary when using results_type new_isolate')

    def _main_mongo(self) -> None:
        """
        Handles a sample according to the given results_type:
        if new_isolate; check whether really new, and if not resequencing, if really new insert into either bad or good
        if reanalysis; check if really new reanalysis, if so update
        if goodqc_validated; if good outcome, reinsert as new_isolate. Else update metadata
        if warningqc_validated; if good outcome, reinsert as new_isolate. Else update metadata
        if resequencing_validated; if good outcome, treat as reanalysis. Else update metadata
        :return: None
        """

        # If statement for results_type
        logger.debug(f"running mainmongo for sample {self._technical_id} with results_type {self._results_type} and species {self._species}")
        if self._results_type == "new_isolate":
            new_json_report = JsonReportDict.from_json(self._jsonfilepath)

            # todo check if fasta path and vcf path are real?
            isolates_findone = MongoRecordDict(self._isolates_collection.find_one({"_id": self._technical_id}))
            if isolates_findone:
                self.__new_resequencing_arrival(new_json_report, isolates_findone, self._isolates_collection)
            else:
                # We're excluding documents that were validated, additionally only documents that were validated with a negative result are still in the warningqc collection
                # Additionally, documents that were negatively validated now have their _id removed in sample_validation_to_mongo.py
                isolates_goodqc_findone = MongoRecordDict(self._isolates_goodqc_collection.find_one({"_id": self._technical_id, "validation": None}))
                isolates_warningqc_findone = MongoRecordDict(self._isolates_warningqc_collection.find_one({"_id": self._technical_id, "validation": None}))
                if isolates_goodqc_findone:
                    self.__new_resequencing_arrival(new_json_report, isolates_goodqc_findone, self._isolates_goodqc_collection)
                elif isolates_warningqc_findone:
                    # unvalidated warningqc isolates are taken care of in the _new_resequencing_arrival function
                    self.__new_resequencing_arrival(new_json_report, isolates_warningqc_findone, self._isolates_warningqc_collection)
                else:
                    self.__process_json_report(new_json_report)
        elif self._results_type == 'goodqc_validated':
            doc = self._isolates_goodqc_collection.find_one({"_id": self._technical_id})
            if doc is None:
                raise MongoMissingValueIsolateCollectionError(
                    f"This goodqc validated technical id ({self._technical_id}) is not present in the isolates_goodqc collections for {self._species} ")
            sample_doc = MongoRecordDict(doc)
            self.__process_mongo_record(sample_doc)
        elif self._results_type == 'warningqc_validated':
            doc = self._isolates_warningqc_collection.find_one({"_id": self._technical_id})
            if doc is None:
                raise MongoMissingValueIsolateCollectionError(
                    f"This warningqc validated technical id ({self._technical_id}) is not present in the isolates_warningqc collections for {self._species} ")
            sample_doc = MongoRecordDict(doc)
            self.__process_mongo_record(sample_doc)

        elif self._results_type == "reanalysis" or self._results_type == 'resequencing_validated':
            try:
                current_results_document = MongoRecordDict(self._mongoquerying.query_docs_by_ids(self._isolates_collection, [self._technical_id])[0])
            except Exception as exceptionmessage:
                send_email(
                    f"{exceptionmessage}\n{traceback.format_exc()}",
                    f"{Path(__file__).name} fail on host {socket.gethostname()}: This reanalysis technical id ({self._technical_id}) is not present in the isolates collections",
                    dont_send_email=self._dont_send_email)
                raise MongoMissingValueIsolateCollectionError(
                    f"{Path(__file__).name} fail on host {socket.gethostname()}: This reanalysis technical id ({self._technical_id}) is not present in the isolates collections")

            if self._results_type == "reanalysis":
                json_report = JsonReportDict.from_json(self._jsonfilepath)
                new_path_to_report = str(self._jsonfilepath.parent)
            else:  # self._results_type == 'resequencing_validated'
                existing_mongo_record = MongoRecordDict(self._isolates_resequencing_collection.find_one({"_id": self._technical_id}))
                json_report = existing_mongo_record.get_json_results()
                new_path_to_report = existing_mongo_record['report_directory']

            self.__new_reanalysis_wrapper(current_results_document, json_report, new_path_to_report)

    def __process_json_report(self, json_report: JsonReportDict) -> MongoRecordDict:
        """
        Function handling the convertion of the initial json report in a Mongo Document stored in MongoDB
        :param json_report: json report containing the results from the pipeline
        :return: a MongoRecordDict object (containing extra data in comparison to the original report)
        """
        json_report["isolates_id"] = self._technical_id
        mongo_records = self.__initialize_mongo_record(json_report)

        good_sample_quality = True
        warning_reasons = None
        if self._results_type == 'new_isolate':
            sample_coreqc_metrics = GetCoreQCMetrics(self._species, self._original_input_format,
                                                     mongo_records['technical_metadata']['data'].get('NanoporeFlowcell', 'illumina')). \
                get_sample_coreqc_metrics()
            check_coreqc_metrics = CheckCoreQCMetrics(self._technical_id, json_report, self._species, self._reportdirectorypath, sample_coreqc_metrics)
            good_sample_quality, rejected_document, warning_reasons = check_coreqc_metrics.check_coreqc_metrics()
            if rejected_document:
                isolates_rejected_coreqc_collection = self._mongoinit.initialise_isolates_rejected_coreqc_collection()

                insert_document_into_rejected_collection(isolates_rejected_coreqc_collection, rejected_document)
                if not self._disable_asb_and_clustering_for_testing:
                    self._asb_instance.send_message_to_queue(AzureServiceBusMessage(self._technical_id, isolates_rejected_coreqc_collection.name))
                logger.info(f"Sample {self._technical_id} failed one or more core QC checks. It was added to the "
                             f"isolates_rejected_coreqc collection.")
                # exit gracefully
                sys.exit()

        self.__process_mongo_record(mongo_records, warning_reasons, good_sample_quality)
        return mongo_records

    def __process_mongo_record(self, mongo_records: MongoRecordDict, warning_reasons: Optional[dict[str, Any]] = None,
                               good_sample_quality: bool = True) -> None:
        """
        Handles and inserts new isolates, whether that be actual new isolates or validated bad samples
        :param mongo_records: results dictionary coming from mongo
        :param good_sample_quality: boolean indicating whether the sample quality is good or bad
        :return: None
        """
        if self._results_type not in ('warningqc_validated', 'goodqc_validated'):  # badqc and goodqc documents have already had their typinghitdictionaries converted to lists and their cgsts/clustering computed
            json_report = mongo_records.get_json_results()
            if not self._disable_asb_and_clustering_for_testing:
                self.__find_hashes_in_results_and_add_to_collection(json_report, 'new_isolate')
            self.__convert_typinghitdictionaries_to_lists(json_report)
            self.__reformat_mykrobe_results(json_report)
            if 'cgmlst' in json_report and not self._disable_asb_and_clustering_for_testing:
                self.__define_cgst_and_run_clustering(json_report)
        if good_sample_quality:
            if self._results_type == 'goodqc_validated' or self._results_type == 'warningqc_validated':
                self.__update_submission_status_after_validation(mongo_records)
                self._isolates_goodqc_collection.delete_one(
                    {'_id': mongo_records["_id"]}) if self._results_type == 'goodqc_validated' else self._isolates_warningqc_collection.delete_one({'_id': mongo_records["_id"]})
                self.__write_document(self._isolates_collection, mongo_records)
                logger.info(f"Wrote new isolate {self._technical_id} and its result to {self._species} database")
            elif self._results_type == 'new_isolate':
                mongo_records['submission_status'] = 'pending_for_submission'
                self.__write_document(self._isolates_goodqc_collection, mongo_records)
                logger.warning(
                    f"New isolate {self._technical_id} succeeded quality control. It's results were written to the 'isolates_goodqc' collection in the {self._species} database")
        else:
            mongo_records['submission_status'] = 'pending_for_submission'
            mongo_records['warning_reasons'] = warning_reasons
            self.__write_document(self._isolates_warningqc_collection, mongo_records)
            logger.info(
                f"New isolate {self._technical_id} failed quality control for one or more checks. It's results were written to the 'isolates_warningqc' collection in the {self._species} database")

    def __new_resequencing_arrival(self, new_json_report: JsonReportDict, document_original: MongoRecordDict,
                                   collection_in: Collection) -> None:
        """
        After an id is found in either isolates, isolates_warningqc or isolates_goodqc; this workflow will determine if
        it really is a resequencing, and if so insert it into isolates_resequencing.
        :param new_json_report: results dictionary that is modified and inserted
        :param document_original: original document including the sample metadata and headers and results
        :param collection_in: the collection that the original sample was in
        :return: None
        """
        # https://git.sciensano.be/bioit/BIGSdb/src/d2a261056221056e56df6aa584563454f6bfec3a/lib/BIGSdb/SubmitPage.pm#L2800
        # 2022-12-20 Check whether resequencing; if resequencing; fasta md5sum should be different from original one. debating whether to store md5 in mongo or not
        # resequencings should be rare, so we can afford multiple finds
        with Path(document_original['fasta_path']).open('r') as handle_ori, Path(self._fastafilepath).open('r') as handle_new:
            md5_original = hashlib.md5(bytes(handle_ori.read(), 'utf-8')).hexdigest()
            md5_new = hashlib.md5(bytes(handle_new.read(), 'utf-8')).hexdigest()
        if md5_original != md5_new:
            # this is an actual resequencing because the fastafilepath is different

            if collection_in == self._isolates_warningqc_collection:
                send_email(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while the sample is present in the isolates_warningqc collection and has not yet been validated, validate the warning qc in bigs before trying to reupload this resequencing.",
                    dont_send_email=self._dont_send_email)
                raise MongoResequencingNoIsolateError(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while the sample is present in the isolates_warningqc collection and has not yet been validated, validate the warning qc in bigs before trying to reupload this resequencing.")
            if collection_in == self._isolates_goodqc_collection:
                send_email(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while the sample is present in the isolates_goodqc collection and has not yet been validated, validate the good qc in bigs before trying to reupload this resequencing.",
                    dont_send_email=self._dont_send_email)
                raise MongoResequencingNoIsolateError(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while the sample is present in the isolates_goodqc collection and has not yet been validated, validate the good qc in bigs before trying to reupload this resequencing.")

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
                raise MongoTooManyResequencingsError(
                    f"WARNING: a resequencing for sample {self._technical_id} was submitted to the isolates_resequencing while one or more resequencings were already present: '{previous_resequencings}' in {self._isolates_resequencing_collection.database.name} on host {socket.gethostname()}, validate the original resequencing in bigs before uploading new resequencings.")
            else:
                new_json_report["isolates_id"] = self._technical_id
                new_isolate = self.__initialize_mongo_record(new_json_report)

                # compute cgST and clustering on the Azure side independent of if quality is good or bad.
                # (there is a missing data filet in the clustering though)
                if not self._disable_asb_and_clustering_for_testing:
                    self.__find_hashes_in_results_and_add_to_collection(new_json_report, 'reanalysis')
                self.__convert_typinghitdictionaries_to_lists(new_json_report)
                self.__reformat_mykrobe_results(new_json_report)
                if 'cgmlst' in new_json_report and not self._disable_asb_and_clustering_for_testing:
                    self.__define_cgst_and_run_clustering(new_json_report)
                new_isolate['submission_status'] = 'pending_for_submission'
                self.__write_document(self._isolates_resequencing_collection, new_isolate)
        else:
            send_email(
                f"The resequencing for  {self._technical_id} was identical to the original isolate or to a previously submitted resequencing",
                dont_send_email=self._dont_send_email)
            raise MongoResequencingAlreadyExistsError(f"The resequencing for  {self._technical_id} was identical to the original isolate or to a previously submitted resequencing")

    def __new_reanalysis_wrapper(self, current_results_document: MongoRecordDict, new_json_report: JsonReportDict, path_to_new_directory: str) -> None:
        """
        Wrapper function for reanalysis and resequencing validated         
        :param current_results_document: the current results document dict in the Mongo collection before applying the reanalysis
        :param new_json_report: the new results document dict, under results for reanalysis, all for resequencing
        :path_to_new_directory: path to the new version of the report
        :return: None
        """
        if not new_json_report.get('cgST'):  # != resequencing_validated, == reanalysis
            if not self._disable_asb_and_clustering_for_testing:
                self.__find_hashes_in_results_and_add_to_collection(new_json_report, 'reanalysis')
            self.__convert_typinghitdictionaries_to_lists(new_json_report)
            self.__reformat_mykrobe_results(new_json_report)

        current_results = current_results_document.get_json_results()
        path_to_report = current_results_document['report_directory']
        if new_json_report["analysis_date"] == current_results["analysis_date"]:
            send_email(f"This ({self._technical_id}) is not a reanalysis but the same results\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise MongoReanalysisDateError(
                f"{Path(__file__).name} fail on host {socket.gethostname()}: This ({self._technical_id}) is not a reanalysis but the same results")
        elif convert_dmyhms_to_ymd(new_json_report["analysis_date"]) < convert_dmyhms_to_ymd(current_results["analysis_date"]):
            send_email(f"These ({self._technical_id}) results seem to be older than the current results\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise MongoReanalysisDateError(
                f"{Path(__file__).name} fail on host {socket.gethostname()}: These ({self._technical_id}) results seem to be older than the current results")
        any_result_changed_new_old, unchanged_results_new_old, changed_results_new_old = self.__check_if_results_changed(current_results, new_json_report)
        # Update new results if really a reanalysis/resequencing where at least one field changed
        if 'cgmlst' in changed_results_new_old and not new_json_report.get('cgST') and not self._disable_asb_and_clustering_for_testing:
            self.__define_cgst_and_run_clustering(new_json_report)
        deltas_new_old = self.__nested_dict_delta(current_results, new_json_report, path_to_report)
        new_results = self.__prepend_string_dot_to_dict_keys(new_json_report, 'results')
        new_results["results.isolates_id"] = self._technical_id
        new_results["results.results_version"] = current_results["results_version"] + 1
        new_results["results.pipeline_hash"] = self._pipeline_hash
        if any_result_changed_new_old:
            new_results["results.changed_version"] = current_results["changed_version"] + 1
            logger.info(f"Writing new changed results and linked to isolate {self._technical_id} in {self._species}")
        else:
            logger.info(
                f"New results are not different from current results for {self._technical_id} in {self._species}, updating analysis dates and db versions.")
        if self._results_type == 'resequencing_validated':
            self.__update_submission_status_after_validation(new_results)

            # Remove the isolate from the resequencing collection to allow for new resequencings
            self._isolates_resequencing_collection.delete_one({'_id': self._technical_id})
        self._isolates_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
            {"_id": self._technical_id}, {
                "$set": {**new_results,
                         "report_directory": path_to_new_directory,
                         "results.results_changed_since_last_version": any_result_changed_new_old,
                         "latest_analysis_date": convert_dmyhms_to_ymd(new_results["results.analysis_date"]),
                         "previous_latest_results_document": self.__write_document(self._old_isolateresults_collection,
                                                                                   MongoRecordDict(dict(deltas_new_old)))}})
        # after having updated the isolates collection, check for changes for HD ODS to respect the order of execution.
        self.__check_if_any_results_for_hd_ods_changed(dict(deltas_new_old))
        if not self._disable_asb_and_clustering_for_testing:
            self._asb_instance.send_message_to_queue(AzureServiceBusMessage(self._technical_id, self._isolates_collection.name))
        logger.info(f"Wrote new results and linked to isolate {self._technical_id} in {self._species}")

    def __check_if_any_results_for_hd_ods_changed(self, deltas_new_old: Dict[str, Any]) -> None:
        """
        Checks if any of the genomic indicators to send to ODS have changed and sets the field
        'changed_since_sent_to_ODS's value to true in the local MongoDB if any have.
        :param deltas_new_old: the deltas between the new and the old results; what needs to be applied on the
        new results to get the old results back.
        :return: None
        """
        with CODES_GENOMIC_ODS.open('r') as handle:
            translation_codes = yaml.safe_load(handle)
        if not translation_codes.get(self._species):
            return
        for variable, variable_info in translation_codes[self._species].items():
            dict_path = variable_info['dict_path'][1:]  # skip the first value which is always 'results' and is not in the delta
            if access_value_in_dict_using_list_as_dictpath(dict_path, deltas_new_old):
                self._isolates_collection.update_one({'_id': deltas_new_old['isolates_id']},
                                                     {'$set': {'changed_since_sent_to_ODS': True,
                                                               'changes_accepted_by_ODS': False}})
                break  # break the loop once at least one change has been discovered

    def __update_submission_status_after_validation(self, new_results: Union[MongoRecordDict, Dict[str, Union[str, object]]]) -> None:
        """
        This function adapts the field "submission_status" in Mongo doc to keep track of the time of validation.
        :param new_results: Mongo doc of the isolate processed for validation
        :return: None
        """
        new_results['validation'] = self._subvaldict
        validation_date = self._subvaldict['date']
        new_results['submission_status'] = f'validated on {validation_date}'

    def __write_document(self, opened_collection: Collection, json_input: MongoRecordDict) -> str:
        """
        Write a document into a collection if the provided document doesn't contain an _id key, then it is autogenerated
        else the _id field that is autogenerated is overwritten by the one provided.
        :param opened_collection: the collection where the document needs to be saved
        :param json_input: the document to store into the collection
        :return: id of inserted document (either pre-given in json_input or auto-generated by Mongo)
        """
        collection_write = opened_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one(
            json_input)

        # Send message to Azure Service Bus
        if 'isolates' in opened_collection.name and not self._disable_asb_and_clustering_for_testing:
            self._asb_instance.send_message_to_queue(AzureServiceBusMessage(
                collection_write.inserted_id, opened_collection.name))
        logger.debug(f"Writing {collection_write.inserted_id} in collection {opened_collection}")
        return collection_write.inserted_id

    def __initialize_mongo_record(self, results: JsonReportDict) -> MongoRecordDict:
        """
        Initialises new isolate dictionary including its results
        :param results: results dictionary to be inserted
        :return: dictionary with results under results key and metadata keys at the same level of the results key
        """
        technical_metadata = self.__retrieve_technical_metadata(results)
        results["pipeline_hash"] = self._pipeline_hash
        results["results_version"] = 1  # this version always increments
        results["changed_version"] = 1  # this version only increments whenever something actually changed
        return MongoRecordDict({
            "_id": self._technical_id,
            "report_directory": str(self._reportdirectorypath),
            "vcf_path": str(self._vcffilepath),
            "vcf_path_unfiltered": str(self._vcffilepath_unfiltered),
            "original_input_format": str(self._original_input_format),
            "fasta_path": str(self._fastafilepath),
            "previous_latest_results_document": None,
            "creation_date": datetime.now(timezone.utc),
            "latest_analysis_date": convert_dmyhms_to_ymd(results["analysis_date"]),
            "technical_metadata": technical_metadata,
            "results": results})

    def __retrieve_technical_metadata(self, results: JsonReportDict) -> JsonReportDict:
        """
        Load the technical metadata in a dictionary and fill in fields that are used when FASTA input is used if
        the input is FASTQ.
        :params results: results dictionary
        :return: dictionary with the technical metadata
        """
        metadata = JsonReportDict.from_json(self._technical_metadata_path)
        metadata.pop('name_pseudonymized', None)
        metadata.pop('species', None)
        if str(self._original_input_format) == 'fastq':
            if not self._mongo_config_provider.is_viral(self._species):
                tx_seq_fltr_meth, cd_seq_assy_meth, tx_seq_assy_meth_ver, ms_genome_cvge, cd_novo_assy, tx_ref_accn \
                    = self.__get_technical_metadata_bacterial_fasta(results)
            else:
                tx_seq_fltr_meth, cd_seq_assy_meth, tx_seq_assy_meth_ver, ms_genome_cvge, cd_novo_assy, tx_ref_accn \
                    = self.__get_technical_metadata_viral_fasta(results)

            metadata['data']['SequenceDataFilteringMethod'] = tx_seq_fltr_meth
            metadata['data']['SequenceAssemblyMethodInfo'] = [{'SequenceAssemblyMethod': cd_seq_assy_meth, 'SequenceAssemblyMethodVersionOrDate': tx_seq_assy_meth_ver}]
            metadata['data']['GenomeCoverage'] = ms_genome_cvge
            metadata['data']['DeNovoAssembly'] = cd_novo_assy
            metadata['data']['ReferenceAccession'] = tx_ref_accn
        return metadata

    def __get_technical_metadata_bacterial_fasta(self, results: JsonReportDict) -> Tuple[str, str, str, str, str, None]:
        """
        Returns the FASTA technical metadata fields if the species is bacterial.
        :params results: results dictionary
        :return: tuple containing the different technical metadata fields
        """
        input_type = results['input_type']
        input_type_abbreviation = 'ilmn' if input_type == 'illumina' else 'ont'
        appendix = self.__get_appendix_from_input_type(input_type)
        tx_seq_fltr_meth = ', '.join([f"downsample factor: {results[f'downsampling_{appendix}']['downsampling_downsample_factor']}",
                                      f"trimming: {results[f'trimming_{input_type}'][f'trim_{input_type_abbreviation}_tool_version']}",
                                      f"filtering of assembly: {results['quast']['assembly_filtering_tool_version']}"
                                      ])
        cd_seq_assy_meth = 'SPAdes'
        tx_seq_assy_meth_ver = results['quast']['assembly_tool_versions']
        ms_genome_cvge = results[f'downsampling_{appendix}']['downsampling_coverage_estimated']
        cd_novo_assy = 'Yes'
        tx_ref_accn = None

        return tx_seq_fltr_meth, cd_seq_assy_meth, tx_seq_assy_meth_ver, ms_genome_cvge, cd_novo_assy, tx_ref_accn

    def __get_technical_metadata_viral_fasta(self, results: JsonReportDict) -> Tuple[str, str, str, str, str, str]:
        """
        Returns the FASTA technical metadata fields if the species is viral.
        Since June 2025, the coverage for viral pathogens is not calculated anymore; this was therefore replaced by 'UNK'.
        :params results: results dictionary
        :return: tuple containing the different technical metadata fields
        """
        input_type = results['input_type']
        input_type_abbreviation = 'ilmn' if input_type == 'illumina' else 'ont'
        appendix = self.__get_appendix_from_input_type(results['input_type'])
        tx_seq_fltr_meth = ', '.join([f"downsample factor: {results[f'downsampling_{appendix}']['downsampling_downsample_factor']}",
                                      f"trimming: {results[f'trimming_{input_type}'][f'trim_{input_type_abbreviation}_tool_version']}"
                                      ])
        cd_seq_assy_meth = 'Other'
        tx_seq_assy_meth_ver = ', '.join([x for x in results['iterative_mapping']['tool_versions']])
        cd_novo_assy = 'No'
        tx_ref_accn = ', '.join(self.__get_ref_ids_from_ref_selection(results['ref_selection'])) if self._species != 'sars_cov_2' else 'NC_045512.2'

        return tx_seq_fltr_meth, cd_seq_assy_meth, tx_seq_assy_meth_ver, 'UNK', cd_novo_assy, tx_ref_accn

    @staticmethod
    def __get_ref_ids_from_ref_selection(ref_selection_dict: dict[str, dict | str]) -> list[str]:
        """
        returns the list of reference ids from reference selection assay (viral pipeline)
        :param ref_selection_dict: reference selection dictionary from MongoDB results
        :return: list of ref ids defined as best match by the reference selection assay
        """
        ref_ids_list = [x['ref_id'] for x in ref_selection_dict.values() if isinstance(x, dict)]
        return ref_ids_list

    @staticmethod
    def __prepend_string_dot_to_dict_keys(input_dictionary: JsonReportDict, prepending: str = 'results') -> Dict[str, Union[str, object]]:
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
            if key == 'quality_checks' or key == 'assembly':
                for subkey in input_dictionary[key]:
                    input_dictionary_copy['.'.join([key, subkey])] = input_dictionary_copy[key][subkey]
                input_dictionary_copy.pop(key)
        keydict = {key: '.'.join([prepending, key]) for key in input_dictionary_copy.keys()}
        return {keydict[key]: value for key, value in input_dictionary_copy.items()}

    @staticmethod
    def __max_temp_allele_name_new_entry(hashed_ad_collection: Collection, locus: str, scheme: str) -> str:
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

    def __find_hashes_in_results_and_add_to_collection(self, json_report: JsonReportDict, mode: str):
        """
        Finds hashes in json output report for multilocus sequence typing schemes and adds these hashes and alleles to a separate collection: new_allele_hashes.
        Also replace the hashes by temporary allele identifiers and purges the sequences to save space
        :param json_report: results dictionary
        :param mode: results_type but resequencing becomes reanalyis
        :return: results
        """
        hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        for typing_scheme in self._mongo_config_provider.sequence_typing_schemes:
            if typing_scheme in json_report:
                for locus_index, allele_info in enumerate(json_report[typing_scheme]['loci']):
                    # check if allele designation is md5 hash (32 char combination of letters andor numbers)
                    if allele_info.get('Allele (hash)'):
                        logger.info('new allele detected')
                        existing_document = hashed_ad_collection.with_options(
                            read_concern=ReadConcern(level="majority")).find_one(
                            {"scheme": typing_scheme, "locus": allele_info['Locus'],
                             "hashed_allele": allele_info['Allele (hash)']})
                        if existing_document is None:
                            temp_allele = self.__max_temp_allele_name_new_entry(hashed_ad_collection, allele_info['Locus'],
                                                                                typing_scheme)
                            self.__write_document(hashed_ad_collection,
                                                  MongoRecordDict({"scheme": typing_scheme,
                                                                   "locus": allele_info['Locus'],
                                                                   "hashed_allele": allele_info['Allele (hash)'],
                                                                   "allele_sequence": allele_info['Allele sequence'],
                                                                   "encountered_count": 1,
                                                                   "resolved_AD": 0,
                                                                   "temp_allele_name": temp_allele,
                                                                   "insertion_date": datetime.now(timezone.utc),
                                                                   "bigsdb_status": "pending"
                                                                   }))
                            json_report[typing_scheme]['loci'][locus_index]['Allele'] = temp_allele  # replace the name of the allele in the results (no hash anymore)
                        else:
                            temp_allele = existing_document["temp_allele_name"]
                            already_present = False
                            if mode == 'reanalysis':
                                hash_old = existing_document["hashed_allele"]
                                if hash_old == allele_info['Allele']:
                                    already_present = True
                                    logger.info('hash/temp allele already present')
                            if mode == 'new_isolate' or (mode == 'reanalysis' and not already_present):
                                hashed_ad_collection.with_options(write_concern=WriteConcern(w="majority")).update_one(
                                    {"_id": existing_document['_id']},
                                    {"$inc": {"encountered_count": 1}})
                                logger.info(f"hashed allele '{allele_info['Allele']}' encounter incremented by one")
                            if existing_document['resolved_AD'] == 0:
                                json_report[typing_scheme]['loci'][locus_index][
                                    'Allele'] = temp_allele  # replace the name of the allele in the results (no hash anymore)
                            else:
                                json_report[typing_scheme]['loci'][locus_index][
                                    'Allele'] = existing_document['resolved_AD']
                        json_report[typing_scheme]['loci'][locus_index].pop('Allele sequence')
                        json_report[typing_scheme]['loci'][locus_index].pop('Allele (hash)')
                        json_report[typing_scheme]['loci'][locus_index].pop('New allele')
                        # In the new output, the identity is not 100% anymore, but the pid to the closest allele.
                        # We need 100% identity for further processing.
                        json_report[typing_scheme]['loci'][locus_index]['% Identity'] = "100.00"

    @staticmethod
    def __check_if_results_changed(current_results: JsonReportDict, new_results: JsonReportDict) -> Tuple[bool, set, set]:
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

        for mainkey, new_value in new_results.items():
            if mainkey == 'quality_checks':
                continue

            if not isinstance(new_value, dict):
                continue

            if mainkey not in current_results:
                print(f"{mainkey} not in current results")
                any_result_changed = True
                changed_results.add(mainkey)
                continue

            # Create a deep copy of the new results and remove version-related subkeys
            mainkey_deepcopy = deepcopy(new_value)
            current_value = current_results[mainkey]

            for subkey in list(mainkey_deepcopy.keys()):
                if isinstance(subkey, str) and ('db_version' in subkey or 'tool_version' in subkey):
                    mainkey_deepcopy.pop(subkey, None)
                    current_value.pop(subkey, None)

            # Compare the modified dictionaries
            if mainkey_deepcopy != current_value:
                print(f"{mainkey} different")
                any_result_changed = True
                changed_results.add(mainkey)
            else:
                unchanged_results.add(mainkey)

        return any_result_changed, unchanged_results, changed_results

    def __nested_dict_delta(self, current_results: JsonReportDict, new_results: JsonReportDict, current_report_path: str) -> JsonReportDict:
        """
        This function calculates the delta between the new results and the current results;
        it returns the changes needed to get from the new results to the current results.
        :param current_results: current mongodb results
        :param new_results: to be inserted results
        :param current_report_path: path to the current report, extracted from Mongo doc.
        :return: dictionary of deltas
        """
        # TODO what with new keys in the new_results (not on assay level)?
        delta_new_old = JsonReportDict({})
        for key, value in current_results.items():
            if key in new_results:
                if isinstance(value, dict) and isinstance(new_results[key], dict):
                    nested_delta = self.__nested_dict_delta(JsonReportDict(value), new_results[key], current_report_path)
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
            delta_new_old['report_directory'] = current_report_path
        return delta_new_old

    def __convert_typinghitdictionaries_to_lists(self, json_report: JsonReportDict) -> None:
        """
        This function aims to reduce the memory usage of hits' metadata by only storing the metadata once in a separate
        collection and storing the results in a list instead.
        Be wary, this method does not create a deepcopy, therefore changes are applied to the input document
        even if the return value's name is modified
        :param json_report: results dictionary
        :return: The converted input document
        """
        hit_metadata: Union[None, Dict[str, Union[object, str, List[str]]]] = self._headers_collection.find_one({'type': 'hit_metadata'})
        if hit_metadata is None:
            inserted_document = self._headers_collection.insert_one({'type': 'hit_metadata'})
            hit_metadata = {'_id': inserted_document.inserted_id}
        results_to_modify = (json_report['results'] if 'results' in json_report else json_report)  # this is not a deepcopy so results will be modified in document as well
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

    def __define_cgst_and_run_clustering(self, json_report: JsonReportDict) -> None:
        """
        Defines the cgST and clusters this cgST with the other cgST's in the database.
        :param json_report: json dict containing all results which are found under the 'results' key
        :return: None
        """
        clustering_input = self._mongoquerying.singledoc_typing_results_by_technicalids_and_scheme(json_report,
                                                                                                   self._technical_id,
                                                                                                   "cgmlst",
                                                                                                   self._headers_collection)
        custom_clustering = MongoCustomClustering(clustering_input[0], clustering_input[1],
                                                  self._species, self._naive_clustering_distance_matrix_file,
                                                  self._mongo_config_provider)
        logger.info(f"Running the clustering for the isolate {self._technical_id}")
        sp_thresholds = MongoClusteringConfigProvider(self._species).get_clustering_thresholds()
        sequence_type = custom_clustering.run_custom_clustering(sp_thresholds)
        json_report["cgST"] = sequence_type

    @staticmethod
    def __get_appendix_from_input_type(input_type: Literal['illumina', 'ont']) -> Literal['fastq_pe', 'fastq_se']:
        """
        Since the Jammy update, certain assays have an appendix to their name which is necessary to be able to
        differentiate between the results of illumina reads and ont reads, especially in case of hybrid input.
        In HERA, we're not expecting hybrid input, but have to deal with this nevertheless.
        E.g. previously the assay would be called 'downsampling' and now it has become 'downsampling_fastq_pe'.
        :param input_type: illumina or ont
        :return: fastq_pe or fastq_se
        """
        if input_type == 'illumina':
            return 'fastq_pe'
        elif input_type == 'ont':
            return 'fastq_se'
        raise NotImplementedError()

    @staticmethod
    def __reformat_mykrobe_results(json_report: JsonReportDict) -> None:
        """
        The mykrobe results from Camel are a list of dicts. This not very useful for the typing inserter into bigsdb,
        and for the flow to the ODS is particularly cumbersome. This function generates a dict of dicts much like the
        loci in cgMLST schemes.
        :param json_report: results dictionary
        :return: None
        """
        if json_report.get('mykrobe'):
            drug_susceptibilities = {info['drug']: info for info in
                                     json_report['mykrobe']['mykrobe_drug_susceptibility']}
            json_report['mykrobe']['mykrobe_drug_susceptibility'] = drug_susceptibilities


if __name__ == '__main__':
    # Configure stdout logger
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)
    args = parse_arguments()
    mongo_config_provider = MongoConfigProvider(args.alternate_dtap)

    connection_string = mongo_config_provider.get_azure_connection_string(args.species)
    if args.connection_string == 'CONNECTION_STRING_ALTERNATE':
        connection_string = mongo_config_provider.alternate_connection_string
    elif args.connection_string == 'CONNECTION_STRING_LOCAL':
        connection_string = mongo_config_provider.get_local_connection_string(args.species)

    # run main
    MainMongo(args.technical_id,
              args.species,
              args.results_type,
              args.pipeline_hash,
              technical_metadata_path=(args.technical_metadata_path if args.technical_metadata_path else None),
              jsonfilepath=(args.jsonfilepath if args.jsonfilepath else None),
              subvaldict=(args.subvaldict if args.subvaldict else None),
              reportdirectorypath=(args.reportdirectorypath if args.reportdirectorypath else None),
              fastafilepath=(args.fastafilepath if args.fastafilepath else None),
              vcffilepath=(args.vcffilepath if args.vcffilepath else None),
              vcffilepath_unfiltered=(args.vcffilepath_unfiltered if args.vcffilepath_unfiltered else None),
              original_input_format=(args.original_input_format if args.original_input_format else None),
              connection_string=connection_string,
              alternate_dtap=args.alternate_dtap,
              dont_send_email=(True if args.dont_send_email else False))
