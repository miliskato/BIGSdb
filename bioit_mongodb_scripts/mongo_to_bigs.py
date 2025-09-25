#!/usr/bin/env python
import argparse
import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import List, Tuple

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql.databaseconnection import DatabaseConnection
from bioit_bigsdb_scripts.components.psql import TblIsolates, TblEavTextHidden, TblMappingTable, \
    TblSchemeMembers, TblTempIsolatesSchemeFields
from bioit_bigsdb_scripts.components.psql.psql_queries import PsqlQueries
from bioit_bigsdb_scripts.main_results_inserter import MainResultsInserter
from bioit_mongodb_scripts.model.json_model import MongoRecordDict, ResultType
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.python_utility_functions import execute_command, get_bigsdb_config_data, \
    get_cgmlst_bigsdb_scheme_id, send_email
from bioit_mongodb_scripts.util.new_temporary_alleles_to_bigs import NewTemporaryAllelesToBigs
from bioit_mongodb_scripts.util.mongo_quickdraw import get_pseudo_id


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=MongoConfigProvider.get_currently_supported_species())
    argument_parser.add_argument('--uploader_mail_address', required=True, type=str)
    argument_parser.add_argument('--single_sample_id', type=str, help=argparse.SUPPRESS)
    return argument_parser.parse_args()


class MongoToBigs:
    """
    Initializing this class will trigger its main function.
    If the current host is a bigsdb host, syncs all samples (or a single one if provided) with the bigsdb database
    """

    def __init__(self, species: str, uploader_mail_address: str, single_sample_id: str = None) -> None:
        """
        Initializes this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param single_sample_id: name of a single sample if only this sample should be synced
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

        self._species = species
        self._single_sample_id = single_sample_id
        self._uploader_mail_address = uploader_mail_address
        # Parse MongoDB config
        self._mongo_config_provider = MongoConfigProvider()
        self._naive_clustering_distance_matrix_file = Path(self._mongo_config_provider.get_naive_clustering_distance_matrix_file(self._species))
        # Parse Bigsdb config
        self._bigsdb_config_data = get_bigsdb_config_data()
        # Open collections
        mongo_init = MongoInitialisation(self._species, self._mongo_config_provider.get_azure_connection_string(self._species), self._mongo_config_provider.dtap)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_warningqc_collection, \
            self._isolates_resequencing_collection, self._isolates_goodqc_collection = \
            mongo_init.initialise_collections()
        self._headers_collection = mongo_init.initialise_headers_collection()
        self._hashed_ad_collection = mongo_init.initialise_hashing_collection()
        self._update_metadata_collection = mongo_init.initialise_update_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = \
            mongo_init.initialise_clustering_collections()
        self._mongoquerying = Mongoquerying()
        # Ope collections local MongoDB
        mongo_init_local = MongoInitialisation(self._species, self._mongo_config_provider.get_local_connection_string(self._species), self._mongo_config_provider.dtap)
        self._mappingtable_collection = mongo_init_local.initialise_mapping_table_collection()
        self._nominative_labtest_clinical_metadata_collection = mongo_init_local.initialise_nominative_labtest_clinical_metadata_collection()
        # Open Bigsdb isolates table
        #self._isolates_psql_tbl = TblIsolates(self._species)

        if not self._mongo_config_provider.is_viral(self._species):
            # Prepare cgmlst cache updater command
            self._cgmlst_bigsdb_scheme_id = get_cgmlst_bigsdb_scheme_id(self._species)

        self._list_of_new_isolates_for_alerts = []  # will remain empty for the viral pathogens
        self._list_of_new_versions_for_alerts = []

    def run_mongo_to_bigs(self) -> tuple[list, list]:
        """
        This runs the insertion of pending documents into bigsdb
        :return: True if something was changed in BIGSdb
        """
        try:
            self._mongo_to_bigs()
            return self._list_of_new_isolates_for_alerts, self._list_of_new_versions_for_alerts
        except Exception as exceptionmessage1:
            traceback1 = traceback.format_exc()
            send_email(f"{exceptionmessage1}\n{traceback.format_exc()}",
                       f'{Path(__file__).name}: Error inserting isolate of {self._species} pipeline to bigsdb for sample {self._single_sample_id} on host {socket.gethostname()}.')
            raise Exception(
                f"{Path(__file__).name} fail on host {socket.gethostname()}: {exceptionmessage1}\n{traceback1}")

    def _mongo_to_bigs(self) -> None:
        """
        Main function
        If the current host is a bigsdb host, syncs all samples (or a single one if provided) with the bigsdb database
        :return: None
        """
        if self._mongo_config_provider.is_viral(self._species):
            self.__mongo_to_bigs_viral()
        else:
            self.__mongo_to_bigs_bacterial()

    def __mongo_to_bigs_bacterial(self) -> None:
        """
        Syncs all bacterial samples with the bigsdb database
        :return: None
        """

        # get list of documents before Temporary alleles insertion so that no new documents with new alleles can be
        # added in the time that it takes between the new alleles to start and the list of documents to be queried
        list_of_documents = self.__get_list_of_documents()

        # tag doc in cluster_membership present in Mongo before the update of temp alleles in BIGSdb.
        # It prevents the insertion of cluster membership that could be added/modified on AZURE after the last alleles update in BIGS
        self._cluster_membership_collection.update_many({}, {'$set': {'select_for_bigsdb_insertion': True}})
        self._st_collection.update_many({}, {'$set': {'select_for_bigsdb_insertion': True}})

        NewTemporaryAllelesToBigs(self._species, self._mongo_config_provider)

        # The cache command needs to be run using method 'full' once before being able to use it with method
        # incremental, check it and execute full if it hadn't been executed yet and if no irregularities are found for this scheme
        self.__check_sql_exceptions_for_cache_update()
        self.__update_scheme_caches_full_once_if_needed()

        # Main insertion into bigsdb for loop + track if changes are done
        for document in list_of_documents:
            isolate_id = self._mappingtable_collection.find_one({'pseudo_id': document['_id']})['_id']
            results_type, new_document_version, cgst_changed = self.__get_results_type(document, isolate_id)
            if not new_document_version:
                continue

            self.__add_isolate_cgst_to_alert_lists(document, isolate_id, results_type, cgst_changed)

            if document.get('validation'):
                # copy validation metadata to results section in order to be able to insert them into BIGSdb
                document['results']['validation'] = document['validation']
            self._mongoquerying.revert_typinghitlists_to_dictionaries(document, self._headers_collection)

            self.__safely_insert_results_and_assembly(document, isolate_id, results_type)

    def __safely_insert_results_and_assembly(self, document: MongoRecordDict, isolate_id: str, results_type: ResultType) -> None:
        """
        Ensures insertion of genomic indicators and assembly of the isolate in BIGSdb using the fail-safe mechanism.
        :param document: mongo db document for this isolate
        :param isolate_id: isolate id
        :param results_type: type of results to insert into bigsdb
        :return: None
        """
        jsonfile = document.get_json_results()
        self.__fail_safe_mechanism(isolate=isolate_id, results_type=results_type)
        MainResultsInserter(isolate_id, self._uploader_mail_address, self._species, results_type,
                            vcf_path=document['vcf_path'], fasta_path=document['fasta_path'], json_results=jsonfile,
                            report_access=document['report_directory'],
                            viral_species=self._mongo_config_provider.is_viral(self._species),
                            isolation_date=document['technical_metadata']['data']['IsolationDate'],
                            nominative_labtest_clinical_metadata_collection=self._nominative_labtest_clinical_metadata_collection)
        if results_type not in ["reanalysis", "resequencing"]:
            with TblMappingTable(self._species) as isolates_mapping_psql_tbl:
                isolates_mapping_psql_tbl.insert_mapping_for_isolate((isolate_id, document['_id'],))
        self.__delete_flagfile(isolate=isolate_id)

    def __add_isolate_cgst_to_alert_lists(self, document: MongoRecordDict, isolate_id: str, results_type: ResultType,
                                          cgst_changed: bool) -> None:
        """
        Function to append isolate_id, cgST, and date_of_isolation to a list that will be used to re-compute BIGSdb alerts
        :param document: Mongo record from isolate collection
        :param isolate_id: isolate id (as found in BIGSdb)
        :param results_type: one of the following string: 'new_isolate', 'goodqc', 'warningqc','resequencing',
        'reanalysis'
        :param cgst_changed: boolean whether the cgST changed
        :return: None
        """
        if results_type == 'new_isolate' or results_type == 'warningqc' or results_type == 'goodqc':
            self._list_of_new_isolates_for_alerts.append(
                {'isolate_name': isolate_id, 'cgST': document['results'].get('cgST'),
                 'isolation_date': document['technical_metadata']['data']['IsolationDate']})

        else:  # if results_type == 'reanalysis' or 'resequencing':
            if cgst_changed:
                self._list_of_new_versions_for_alerts.append(
                    {'isolate_name': isolate_id, 'cgST': document['results'].get('cgST'),
                     'isolation_date': document['technical_metadata']['data']['IsolationDate']})
                with TblTempIsolatesSchemeFields(self._species, self._cgmlst_bigsdb_scheme_id) as temp_isolates_scheme_fields:
                    temp_isolates_scheme_fields.delete_profile((isolate_id,))

    def __update_scheme_caches_full_once_if_needed(self) -> None:
        """
        Checks whether a full update of the scheme caches of the cgmlst scheme is needed (only the first time when
        the table doesn't exist), and executes the full scheme cache update if needed.
        :return: None
        """
        with DatabaseConnection(self._species, 'isolates') as isolates_psql_db:
            temp_scheme_exists: List[Tuple[bool]] = isolates_psql_db.execute_query(PsqlQueries.SEL_TABLE_EXISTS,
                                                                                   (f'temp_scheme_{self._cgmlst_bigsdb_scheme_id}',))
            if not temp_scheme_exists[0][0]:
                cache_command = f'/home/bigsdb/BIGSdb/scripts/maintenance/update_scheme_caches.pl ' \
                                f'--database bigsdb_{self._species}_isolates --schemes {self._cgmlst_bigsdb_scheme_id} ' \
                                f'--method full'
                execute_command(cache_command, Path(os.getcwd()))

    def __mongo_to_bigs_viral(self) -> None:
        """
        Syncs all viral samples with the bigsdb database, using an alternative and simplified version of the bacterial
        method that skips all step involving schemes.
        :return: None
        """
        list_of_documents = self.__get_list_of_documents()
        for document in list_of_documents:
            isolate_id = self._mappingtable_collection.find_one({'pseudo_id': document['_id']})['_id']
            results_type, new_document_version, _ = self.__get_results_type(document, isolate_id)
            if not new_document_version:
                continue
            if document.get('validation'):
                # copy validation metadata to results section in order to be able to insert them into BIGSdb
                document['results']['validation'] = document['validation']
            self.__safely_insert_results_and_assembly(document, isolate_id, results_type)

    def __check_sql_exceptions_for_cache_update(self) -> None:
        """
        Checks for irregularities in BIGSdb dbs that would lead to an error of the cache update. If one of them is found,
        an exception is raised.
        :return: None
        """
        with TblSchemeMembers(self._species, 'seqdef') as seqdef_schememembers_psql_tbl:
            scheme_members_exist: List[Tuple[bool]] = seqdef_schememembers_psql_tbl.check_scheme_member_presence((self._cgmlst_bigsdb_scheme_id,))
            if not scheme_members_exist[0][0]:
                raise RuntimeError(
                    f"Update of the cache cannot be computed on {socket.gethostname()} for scheme {self._cgmlst_bigsdb_scheme_id} because no scheme members were found in seqdef, "
                    f"check the metadata collection in Mongo to ensure that seqdef has been populated properly")

        with DatabaseConnection(self._species, 'seqdef') as seqdef_psql_db:
            mv_scheme_exists: List[Tuple[bool]] = seqdef_psql_db.execute_query(PsqlQueries.SEL_TABLE_EXISTS, (f'mv_scheme_{self._cgmlst_bigsdb_scheme_id}',))
            if not mv_scheme_exists[0][0]:
                raise RuntimeError(
                    f"update of the cache cannot be computed on {socket.gethostname()} because mv_scheme_{self._cgmlst_bigsdb_scheme_id} is missing. Try to repair the scheme "
                    f"from bigsdb seqdef curator interface using the 'Configuration repair' tool")

    def __get_list_of_documents(self) -> List[MongoRecordDict]:
        """
        Gets the list of documents, = all if no single_sample_id, else list of single document
        :return: list of documents (dictionaries)
        """
        if self._single_sample_id:
            pseudo_id = get_pseudo_id(self._species, self._single_sample_id)
            query_single = MongoRecordDict(self._isolates_collection.find_one({'_id': pseudo_id}))
            if not query_single:
                raise Exception(f"Can not find document with _id '{self._single_sample_id}'")
            list_of_documents = [query_single]
            for document in list_of_documents:
                document.set_isolate_id(pseudo_id)

        else:
            list_of_documents = list(map(lambda x: MongoRecordDict(x), self._isolates_collection.find()))
            for document in list_of_documents:
                document.set_isolate_id(document['_id'])

        return list_of_documents

    def __get_results_type(self, document: MongoRecordDict, isolate_id: str) -> Tuple[ResultType, bool, bool]:
        """
        Checks whether the document is a new_isolate or a reanalysis and whether the for loop should continue (bool
        output). The for loop should continue to the next document if the reanalysis is not different.
        :param document: dictionary of the results of the current isolate
        :param isolate_id: the id of the isolate
        :return: results_type and whether for loop should continue to next sample (True) or proceed (False) and
        boolean whether the cgST changed; always True if results_type is not reanalysis or resequencing
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            sample_presence = isolates_psql_tbl.count_isolate((isolate_id,))
        # is_sample_failed: isolate into bigsdb was started but failed during insertion.
        # if argument "new_isolate" is passed to main_results_inserter and it finds the flag,
        # it will remove the isolate and the flag, and then recreate the flag and start insertion again.
        if_sample_failed = sample_presence[0][0] == 1 and (
                    Path(self._bigsdb_config_data['failsafe']['flag_dir']) / '.'.join(
                     [isolate_id, self._bigsdb_config_data['failsafe']['flag_append']])).is_file()

        different_version = True
        cgst_changed = True
        if sample_presence[0][0] == 0 or (if_sample_failed and document.get("results").get("results_changed_since_last_version") is None):
            results_type = "new_isolate"
        elif document.get_validation_type():
            results_type = document.get_validation_type()
            if results_type == 'resequencing' or results_type == 'warningqc' or results_type == 'goodqc':
                different_version, cgst_changed = self.___check_if_reanalysis_different(document, isolate_id)
                if results_type == 'warningqc' or results_type == 'goodqc':
                    results_type = "reanalysis"
        else:
            results_type = "reanalysis"
            different_version, cgst_changed = self.___check_if_reanalysis_different(document, isolate_id)

        return results_type, different_version, cgst_changed

    def ___check_if_reanalysis_different(self, document: MongoRecordDict, isolate_id: str) -> (bool, bool):
        """
        Checks if the reanalysis is different or not, outside this function: continues the for loop,
        it is called in, to the next sample if not different
        :param document: document dictionary
        :param isolate_id: name of the isolate
        :return: boolean whether version is different or not and boolean whether the cgst changed
        """
        with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
            mongo_results_changed_version_bigs_query = isolates_eavth_psql_tbl.select_mongo_resultsversion((isolate_id,))
        # as of 2022/12/22 mongo_results_version in bigs is changed version
        mongo_results_changed_version_bigs = int(mongo_results_changed_version_bigs_query[0][0])

        different_version = False
        cgst_changed = False
        new_results = document.get_json_results()
        if new_results['changed_version'] == int(mongo_results_changed_version_bigs):
            # results are same so do nothing
            logging.info(f"results_version might be different, but changed_version same in mongodb and bigsdb for "
                         f"{isolate_id}")
        else:
            different_version = True
            # skip cgst check for virus
            if self._mongo_config_provider.is_viral(self._species):
                return different_version, cgst_changed
            # check whether the cgST that is currently in the db for the isolate is the same as the
            # cgST of the new version in Mongo.
            with TblIsolates(self._species) as isolates_psql_tbl:
                cgst_query_result = isolates_psql_tbl.select_current_cgst_of_isolate((self._cgmlst_bigsdb_scheme_id, isolate_id))
            if (cgst_query_result[0][0] is None and new_results.get('cgST') is not None) or (
                    cgst_query_result[0][0] is not None and int(cgst_query_result[0][0]) != new_results.get('cgST')):
                cgst_changed = True
        return different_version, cgst_changed


    def ___make_flagfilepath(self, isolate: str) -> Path:
        """
        Returns the flag file path
        :param isolate: BIGSdb isolate name
        :return: flag file path
        """
        return Path(self._bigsdb_config_data['failsafe']['flag_dir']) / '.'.join(
            [isolate, self._bigsdb_config_data['failsafe']['flag_append']])

    def __fail_safe_mechanism(self, isolate: str, results_type: ResultType) -> None:
        """
        Creates a flagfile if insertion is started and no flagfile is present.
        else insertion is started and flag file is present: remove highest version of sample and
        reinsert if multiple versions, if only one version, sample is reinserted in the main workflow below
        :param isolate: BIGSdb isolate name
        :param results_type: one of the following string: 'new_isolate', 'goodqc', 'warningqc','resequencing',
        'reanalysis'
        :return: None
        """
        try:
            if not Path(self._bigsdb_config_data['failsafe']['flag_dir']).is_dir():
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).mkdir(parents=True, exist_ok=True)
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).chmod(0o755)
            flagfilepath = self.___make_flagfilepath(isolate)
            if flagfilepath.is_file() and not (
                    results_type in ['reanalysis', 'resequencing']):
                logging.warning(
                    f"fail safe mechanism detects that the bigsdb insertion for sample {isolate} was started but did not finish. Removing {isolate} from Bigsdb to be able to restart inserting.")
                with TblIsolates(self._species) as isolates_psql_tbl:
                    isolates_psql_tbl.delete_isolate([isolate])
                self._nominative_labtest_clinical_metadata_collection.update_one({'_id': isolate},
                                                                                 {'$set': {
                                                                                     'inserted_into_bigsdb': False}})
            else:
                flagfilepath.touch()
                flagfilepath.chmod(0o755)
                logging.info(f"flagfilepath {flagfilepath}")
        except Exception:
            raise Exception(
                f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}. Traceback: {traceback.format_exc()}")

    def __delete_flagfile(self, isolate: str) -> None:
        """
        delete the flagfile created for the fail-safe mechanism
        :param isolate: BIGSdb isolate name
        :return: None, Removes flagfile
        """
        flagfilepath: Path = self.___make_flagfilepath(isolate)
        try:
            flagfilepath.unlink()
        except Exception:
            raise Exception(
                f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}. Traceback: {traceback.format_exc()}")


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

    # Parse arguments
    args = parse_arguments()

    # run main
    mongo_to_bigs_instance = MongoToBigs(args.species, args.uploader_mail_address,
                                         single_sample_id=(args.single_sample_id if args.single_sample_id else None))
    mongo_to_bigs_instance.run_mongo_to_bigs()
