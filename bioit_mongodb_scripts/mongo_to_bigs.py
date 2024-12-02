#!/usr/bin/env python
# Hybrid between Bigs components and Mongodb components
# to be executed on bigs host of choice
# /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_new/bioit_mongodb_scripts/mongo_to_bigs.py --species listeria --uploader_mail_address bioit@sciensano.be --pyvenvpythonpath /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9

import argparse
import datetime
import logging
import os
import socket
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql.databaseconnection import DatabaseConnection
from bioit_bigsdb_scripts.components.psql import TblAlleleDesignations, TblIsolates, TblEavTextHidden, TblMappingTable, \
    TblSchemes
from bioit_bigsdb_scripts.components.psql.psql_queries import PsqlQueries
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data
from bioit_bigsdb_scripts.insert_assembly import insert_assembly
from bioit_bigsdb_scripts.genedetection_intopsql import GeneDetectionIntoPsql
from bioit_bigsdb_scripts.main_results_inserter import MainResultsInserter
from bioit_mongodb_scripts.model.json_model import MongoRecordDict, ResultType
from bioit_bigsdb_scripts.Typing_alleles_intopsql import TypingAllelesIntoPsql
from bioit_bigsdb_scripts.Typing_loci_intopsql import TypingLociIntoPsql
from bioit_bigsdb_scripts.Typing_schemeprofiles_intopsql import TypingSchemeProfilesIntoPsql
from bioit_mongodb_scripts.util.alerts_to_bigs import AlertsToBigs
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.mongo_to_bigs_nominative import MongoToBigsNominative
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email
from bioit_mongodb_scripts.util.new_clustering_info_to_bigs import NewClusteringInfoToBigs
from bioit_mongodb_scripts.util.new_temporary_alleles_to_bigs import NewTemporaryAllelesToBigs
from bioit_mongodb_scripts.util.samples_to_validation_bigs import SamplesToValidationBigs
from bioit_mongodb_scripts.util.command.command import Command


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    argument_parser.add_argument('--uploader_mail_address', required=True, type=str)
    argument_parser.add_argument('--single_sample_id', type=str, help=argparse.SUPPRESS)
    return argument_parser.parse_args()


class MongoToBigs:
    """
    Initializing this class will trigger its main function.
    If the current host is a bigsdb host, syncs all samples (or a single one if provided) with the bigsdb database
    """

    def __init__(self, species: str, uploader_mail_address: str, single_sample_id: str = None,
                 mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Initializes this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param single_sample_id: name of a single sample if only this sample should be synced
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

        self._species = species
        self._single_sample_id = single_sample_id
        self._uploader_mail_address = uploader_mail_address
        # Parse MongoDB config
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()
        self._naive_clustering_distance_matrix_file = Path(
            self._mongo_config_data['naive_clustering_distance_matrix_file'].replace('species', self._species).replace(
                'dtap', self._mongo_config_data.get('dtap')).replace('.bioit_database', '.bioit_database_azure'))
        # Parse Bigsdb config
        self._bigsdb_config_data = get_bigsdb_config_data()
        # Open collections
        self.initialisation = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                                  selected_connection_string='CONNECTION_STRING_AZURE')
        self._mongoinit = self.initialisation
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, \
            self._isolates_resequencing_collection = self._mongoinit.initialise_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._hashed_ad_collection = self._mongoinit.initialise_hashing_collection()
        self._update_metadata_collection = self._mongoinit.initialise_update_collection()
        self._st_collection, self._cluster_membership_collection, self._cluster_merging_collection = \
            self._mongoinit.initialise_clustering_collections()
        self._mongoquerying = Mongoquerying()
        # Ope collections local MongoDB
        self._mongoinit_local = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                                    selected_connection_string='CONNECTION_STRING_LOCAL')
        self._mappingtable_collection = self._mongoinit_local.initialise_mapping_table_collection()
        self._nominative_labtest_clinical_metadata_collection = self._mongoinit_local.initialise_nominative_labtest_clinical_metadata_collection()
        # Open Bigsdb isolates table
        self._isolates_psql_tbl = TblIsolates(self._species)

        # Prepare cgmlst cache updater command
        with TblSchemes(self._species, 'isolates') as isolates_schemes_psql_tbl:
            self._cgmlst_bigsdb_scheme_id = isolates_schemes_psql_tbl.select_scheme_id_cgmlst()[0][0]

        cache_command = f'/home/bigsdb/BIGSdb/scripts/maintenance/update_scheme_caches.pl ' \
                        f'--database bigsdb_{self._species}_isolates --schemes {self._cgmlst_bigsdb_scheme_id} ' \
                        f'--method daily_replace'
        self._cache_command_object = Command(cache_command)

        # Prepare
        self._list_of_new_isolates_for_alerts = []
        self._list_of_new_versions_for_alerts = []

        # Execute main function
        self._exception_in_alerts = False
        try:
            self._mongo_to_bigs()
        except Exception as exceptionmessage1:
            """
            If an insertion into bigsdb fails, the alerts for the succeeded insertions need to be evaluated,
            because else they would not be evaluated at all
            for this purpose the cache first needs to be updated after having inserted new isolates/cgsts
            (the cgst needs to come from the seqdef db).
            """
            self._exceptionmessage1 = exceptionmessage1
            self._traceback1 = traceback.format_exc()

            self._run_alerts_to_bigs_upon_exception()

            send_email(f"{self._exceptionmessage1}\n{self._traceback1}")
            raise Exception(
                f"{Path(__file__).name} fail on host {socket.gethostname()}: {self._exceptionmessage1}\n{self._traceback1}")

    def _mongo_to_bigs(self) -> None:
        """
        Main function
        If the current host is a bigsdb host, syncs all samples (or a single one if provided) with the bigsdb database
        :return: None
        """
        # Check if dbs were updated and update bigsdb accordingly
        self.__update_bigsdb_psql_if_needed()

        # get list of documents before Temporary alleles insertion so that no new documents with new alleles can be
        # added in the time that it takes between the new alleles to start and the list of documents to be queried
        list_of_documents = self.__get_list_of_documents()

        # tag doc in cluster_membership present in Mongo before the update of temp alleles in BIGSdb.
        # It prevents the insertion of cluster membership that could be added/modified on AZURE after the last alleles update in BIGS
        self._cluster_membership_collection.update_many({}, {'$set': {'select_for_bigsdb_insertion': True}})
        self._st_collection.update_many({}, {'$set': {'select_for_bigsdb_insertion': True}})

        NewTemporaryAllelesToBigs(self._species, mongo_config_data=self._mongo_config_data)

        # The cache command needs to be run using method 'full' once before being able to use it with method
        # incremental, check it and execute full if it hadn't been executed yet
        self.__update_scheme_caches_full_once_if_needed()

        # send bad samples from the badqc_isolates collection to BIGSdb
        SamplesToValidationBigs(self._species, mongo_config_data=self._mongo_config_data)

        # Main insertion into bigsdb for loop + track if changes are done
        changes_in_bigsdb = False
        for document in list_of_documents:
            isolate_id = self._mappingtable_collection.find_one({'pseudo_id': document['_id']})['_id']
            results_type, new_document_version, cgst_changed = self.__get_results_type(document, isolate_id)
            if not new_document_version:
                continue

            self.__add_isolate_cgst_to_alert_lists(document, isolate_id, results_type, cgst_changed)

            # continuation of for loop:
            # extract json file to be given to bigs
            if document.get('validation'):
                # copy validation metadata to results section in order to be able to insert them into BIGSdb
                document['results']['validation'] = document['validation']
            self._mongoquerying.revert_typinghitlists_to_dictionaries(document, self._headers_collection)
            jsonfile = document.get_json_results()

            self.__fail_safe_mechanism(self._isolates_psql_tbl, isolate=isolate_id, results_type=results_type)

            MainResultsInserter(isolate_id, self._uploader_mail_address, self._species, results_type,
                                vcf_path=document['vcf_path'], json_results=jsonfile,
                                report_access=document['report_directory'],
                                mongo_dtap=self._mongo_config_data.get('dtap'),
                                isolation_date=document['technical_metadata']['data']['IsolationDate'],
                                nominative_labtest_clinical_metadata_collection=self._nominative_labtest_clinical_metadata_collection)

            self.__insert_assembly_into_bigs(results_type, document, isolate_id)

            if results_type not in ["reanalysis", "resequencing"]:
                with TblMappingTable(self._species) as isolates_mapping_psql_tbl:
                    isolates_mapping_psql_tbl.insert_mapping_for_isolate((isolate_id, document['_id'],))

            self.__delete_flagfile(isolate=isolate_id)

            changes_in_bigsdb = True

        if changes_in_bigsdb:
            # Run clustering and new cgST insertion before cache update
            NewClusteringInfoToBigs(self._species, self._naive_clustering_distance_matrix_file,
                                    self._cgmlst_bigsdb_scheme_id, mongo_config_data=self._mongo_config_data)

            # Update cache again before alerts implementation because new isolates won't have cgST's but are needed for alerts implementation
            self._cache_command_object.run(Path(os.getcwd()))
            if self._cache_command_object.returncode != 0:
                send_email(f"update of the cache to display the cgsts of new isolates failed on host {socket.gethostname()}")
                raise RuntimeError(f"update of the cache to display the cgsts of new isolates failed on host {socket.gethostname()}")

            # Insert nominative and labtest metadata after having done everything else except the alerts in order to not break the alerts 'failsafe'
            MongoToBigsNominative(self._species, self._mongo_config_data, dont_send_email=True)

        # Run Alerts to bigs after updating the cache because it accesses a SQL table that is updated by the cache updater.
        # also run it after having inserted all isolates into bigsdb
        try:
            if len(self._list_of_new_isolates_for_alerts + self._list_of_new_versions_for_alerts) > 0:
                AlertsToBigs(self._list_of_new_isolates_for_alerts, self._list_of_new_versions_for_alerts, self._species,
                             self._cgmlst_bigsdb_scheme_id, self._naive_clustering_distance_matrix_file)
        except:
            self._exception_in_alerts = True
            raise

    def __update_bigsdb_psql_if_needed(self) -> None:
        """
        This function checks whether a new dbupdate occured in Azure and updates all info in Bigsdb accordingly.
        :return: None
        """
        last_schema_update_date_document = self._update_metadata_collection.find_one({'metadata': 'last_dbupdate_insertion_date'})
        last_dbupdate_date = self._update_metadata_collection.find_one({'metadata': 'last_dbupdate_date'})['last_update_date']
        if not last_schema_update_date_document or last_dbupdate_date > last_schema_update_date_document['last_update_date']:
            # Run the temporary id replacer
            self.___replace_tempids()

            # Insert new typing loci, alleles, typing profiles & gene detection alleles into psql
            TypingLociIntoPsql([self._species], dont_send_email=True)
            TypingAllelesIntoPsql([self._species], dont_send_email=True)
            TypingSchemeProfilesIntoPsql([self._species], dont_send_email=True)
            GeneDetectionIntoPsql([self._species], do_not_recalculate=True, dont_send_email=True)
            # update last insertion date
            self._update_metadata_collection.update_one({'metadata': 'last_dbupdate_insertion_date'},
                                                        {'$set': {'last_update_date': datetime.datetime.now(
                                                            datetime.timezone.utc)}}, upsert=True)

    def __add_isolate_cgst_to_alert_lists(self, document: MongoRecordDict, isolate_id: str, results_type: ResultType,
                                          cgst_changed: bool) -> None:
        """
        Function to append isolate_id, cgST, and date_of_isolation to a list that will be used to re-compute BIGSdb alerts
        :param document: Mongo record from isolate collection
        :param isolate_id: isolate id (as found in BIGSdb)
        :param results_type: one of the following string: 'new_isolate','badqc','resequencing','reanalysis'
        :param cgst_changed: boolean whether the cgST changed
        :return: None
        """
        if results_type == 'new_isolate' or results_type == 'badqc':
            self._list_of_new_isolates_for_alerts.append(
                {'isolate_name': isolate_id, 'cgST': document['results'].get('cgST'),
                 'isolation_date': document['technical_metadata']['data']['IsolationDate']})

        else:  # if results_type == 'reanalysis' or 'resequencing':
            if cgst_changed:
                self._list_of_new_versions_for_alerts.append(
                    {'isolate_name': isolate_id, 'cgST': document['results'].get('cgST'),
                     'isolation_date': document['technical_metadata']['data']['IsolationDate']})

    def ___replace_tempids(self) -> None:
        """
        Replaces the temporary ids of alleles in bigsdb by actual allele numbers found in Pubmlst/Enterobase and
        indicated as such by Azure: "resolved_AD".
        :return: None
        """
        documents_list = [document for document in self._hashed_ad_collection.find(
            {'scheme': {'$in': self._mongo_config_data['schemes_sequence_typing']},
             'resolved_AD': {'$ne': 0}, 'replaced_in_bigs_date': {'$exists': False}})]

        with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl:
            for hash_document in documents_list:
                isolates_ad_psql_tbl.update_designations(
                    (hash_document['resolved_AD'], hash_document['locus'], hash_document['hashed_allele']))
        self._hashed_ad_collection.update_many(
            {'_id': {'$in': [hash_document['_id'] for hash_document in documents_list]}},
            {'$set': {'replaced_in_bigs_date': datetime.datetime.now()}})

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
                cache_command_object = Command(cache_command)
                cache_command_object.run(Path(os.getcwd()))
                if cache_command_object.returncode != 0:
                    send_email(f"update of the cache to display the clustering failed on host {socket.gethostname()}")
                    raise RuntimeError(
                        f"update of the cache to display the clustering failed on host {socket.gethostname()}")

    def __get_list_of_documents(self) -> List[MongoRecordDict]:
        """
        Gets the list of documents, = all if no single_sample_id, else list of single document
        :return: list of documents (dictionaries)
        """
        if self._single_sample_id:
            pseudo_id = str(self._mappingtable_collection.find_one({'_id': self._single_sample_id})['pseudo_id'])
            query_single = MongoRecordDict(self._isolates_collection.find_one({'_id': pseudo_id}))
            if not query_single:
                send_email(f"Can not find document with _id '{self._single_sample_id}', check the validation status")
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
        Checks whether the document is a new_isolate or a reanalysis and whether the for loop should continue (bool output).
        The for loop should continue to the next document if the reanalysis is not different.
        :param document: dictionary of the results of the current isolate
        :param isolate_id: the id of the isolate
        :return: results_type and whether for loop should should continue to next sample (True) or proceed (False) and
        boolean whether the cgST changed; always True if results_type is not reanalysis or resequencing
        """
        sample_presence = self._isolates_psql_tbl.count_isolate((isolate_id,))
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
            if results_type == 'resequencing' or (results_type == 'badqc' and sample_presence[0][0] == 1):
                different_version, cgst_changed = self.___check_if_reanalysis_different(document, isolate_id)
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

            # check whether the cgST that is currently in the db for the isolate is the same as the
            # cgST of the new version in Mongo.
            cgst_query_result = self._isolates_psql_tbl.select_current_cgst_of_isolate((self._cgmlst_bigsdb_scheme_id, isolate_id))
            if (cgst_query_result[0][0] is None and new_results.get('cgST') is not None) or int(cgst_query_result[0][0]) != new_results.get('cgST'):
                cgst_changed = True
        return different_version, cgst_changed

    def __insert_assembly_into_bigs(self, results_type: ResultType, document: MongoRecordDict, isolate_id: str) -> None:
        """
        Fetches the assembly from Azure and inserts into bigsdb when applicable
        :param results_type: new_isolate or reanalysis
        :param document: dictionary of the results of the current isolate
        :param isolate_id: the id of the isolate
        :return: None
        """
        # In case of an actual reanalysis, the MainResultsInserter handles the assembly transfer between
        # isolates and we do not want to scp the assembly from Azure
        if not results_type == 'reanalysis':
            fasta_name = Path(document['fasta_path']).name
            fasta_path_remote = Path(document['report_directory']) / 'assembly' / fasta_name
            with tempfile.NamedTemporaryFile(dir=self._mongo_config_data.get('temp_dir'), mode="w") as temp_fasta:
                temp_fasta_path = Path(self._mongo_config_data.get('temp_dir')) / temp_fasta.name
                scp_command = f"scp -o StrictHostKeyChecking=no -i /home/bigsdb/.ssh/.id_rsa_reportsapi bigsdb@{self._mongo_config_data.get('azure_reportsapi_ip')}:{fasta_path_remote} {str(temp_fasta_path)}"
                scp_cmd = Command(scp_command)
                scp_cmd.run(Path(self._mongo_config_data.get('temp_dir')))
                if scp_cmd.returncode != 0:
                    raise Exception(
                        f"scp command to copy fasta from Azure to onsite failed: {scp_cmd.stderr}\nscp command: {scp_command}")

                insert_assembly(isolate_id, self._species, temp_fasta_path, results_type)
                logging.info(f"Inserted assembly for isolate {isolate_id} into bigsdb")

                # The resequencing is for now disable as also commented in samples_to_validation_bigs.py
                # if document.get_validation_type() == 'resequencing': #is it the place to check that isolation date are different, I don't think so
                #     last_two_validation_dates = self._isolates_psql_tbl.select_validationdate_for_isolate(
                #         (isolate_id,))
                #     # select to check that the previous version's validation date is different from the current
                #     if last_two_validation_dates[0][0] != last_two_validation_dates[1][0]:
                #         # revert the changes done in maininserter that move the assembly to the newest version
                #         with TblSequenceBin(self._species) as isolates_seqbin_psql_tbl:
                #             isolates_seqbin_psql_tbl.revert_sequencebin_newversion([isolate_id])
                #         with TblSeqBinStats(self._species) as isolates_seqbinstats_psql_tbl:
                #             isolates_seqbinstats_psql_tbl.revert_seqbinstats_newversion([isolate_id])
                #         insert_assembly(isolate_id, self._species, temp_fasta_path, results_type)
                #     logging.info(f"Wrote new results version for {isolate_id} to bigsdb")

    def __del__(self) -> None:
        """
        Closes the isolates psql table when the class is closed
        :return: None
        """
        self._isolates_psql_tbl.close()

    def _run_alerts_to_bigs_upon_exception(self) -> None:
        """
        If an insertion into BIGSdb fails, the alerts for the succeeded insertions need to be evaluated,
        because else they would not be evaluated at all
        for this purpose the cache first needs to be updated after having inserted new isolates/cgsts
        (the cgst needs to come from the seqdef db).
        :return: None
        """
        self._cache_command_object.run(Path(os.getcwd()))
        if self._cache_command_object.returncode != 0:
            send_email(f"update of the cache to display the clustering failed on host {socket.gethostname()}")
            raise RuntimeError(
                f"update of the cache to display the clustering failed on host {socket.gethostname()}")

        # then run the alerts implementation for distance matrices
        # ofcourse this can fail too, therefore we encapsulate it in another try except
        if len(self._list_of_new_isolates_for_alerts + self._list_of_new_versions_for_alerts) > 0 and not \
                self._exception_in_alerts:
            try:
                AlertsToBigs(self._list_of_new_isolates_for_alerts, self._list_of_new_versions_for_alerts,
                             self._species, self._cgmlst_bigsdb_scheme_id, self._naive_clustering_distance_matrix_file)
            except Exception as exceptionmessage2:
                traceback2 = traceback.format_exc()
                send_email(f"Failure 1: {self._exceptionmessage1}\n{self._traceback1}\n"
                           f"Failure 2: {exceptionmessage2}\n{traceback2}",
                           subject=f"{Path(__file__).name} double fail on host {socket.gethostname()}")
                raise Exception(f"{Path(__file__).name} double fail on host {socket.gethostname()}: "
                                f"Failure 1: {self._exceptionmessage1}\n{self._traceback1}\n"
                                f"Failure 2: {exceptionmessage2}\n{traceback2}")

    def ___make_flagfilepath(self, isolate: str) -> Path:
        """
        Returns the flag file path
        :param isolate: BIGSdb isolate name
        :return: flag file path
        """
        return Path(self._bigsdb_config_data['failsafe']['flag_dir']) / '.'.join(
            [isolate, self._bigsdb_config_data['failsafe']['flag_append']])

    def __fail_safe_mechanism(self, isolates_psql_tbl: TblIsolates, isolate: str, results_type: ResultType) -> None:
        """
        Creates a flagfile if insertion is started and no flagfile is present.
        else insertion is started and flag file is present: remove highest version of sample and
        reinsert if multiple versions, if only one version, sample is reinserted in the main workflow below
        :param isolates_psql_tbl: isolates db isolates table/ connection instance for a given species
        :param isolate: BIGSdb isolate name
        :param results_type: one of the following string: 'new_isolate','badqc','resequencing','reanalysis'
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
                isolates_psql_tbl.delete_isolate([isolate])
                self._nominative_labtest_clinical_metadata_collection.update_one({'_id': isolate},
                                                                                 {'$set': {
                                                                                     'inserted_into_bigsdb': False}})
            else:
                flagfilepath.touch()
                flagfilepath.chmod(0o755)
                logging.info(f"flagfilepath {flagfilepath}")
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")

    def __delete_flagfile(self, isolate: str) -> None:
        """
        :param isolate: BIGSdb isolate name
        :return: None, Removes flagfile
        """
        flagfilepath: Path = self.___make_flagfilepath(isolate)
        try:
            flagfilepath.unlink()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

    # Parse Mongo config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    MongoToBigs(args.species, args.uploader_mail_address,
                single_sample_id=(args.single_sample_id if args.single_sample_id else None),
                mongo_config_data=mongo_config_data)
