#!/usr/bin/env python
# Hybrid between Bigs components and Mongodb components
# to be executed on bigs host of choice
# /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_new/bioit_mongodb_scripts/mongo_to_bigs.py --species listeria --uploader_mail_address bioit@sciensano.be --pyvenvpythonpath /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9

import argparse
import json
import logging
import socket
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, List
import os

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblIsolates, TblEavTextHidden, TblSequenceBin, TblSeqBinStats, TblSchemes
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data
from bioit_bigsdb_scripts.insert_assembly import insert_assembly
from bioit_bigsdb_scripts.main_results_inserter import MainResultsInserter
from bioit_mongodb_scripts.util.alerts_to_bigs import AlertsToBigs
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email, convert_dmyhms_to_dateobj
from bioit_mongodb_scripts.util.new_clustering_info_to_bigs import NewClusteringInfoToBigs
from bioit_mongodb_scripts.util.samples_to_validation_bigs import samples_to_validation_bigs
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
    def __init__(self, species: str, uploader_mail_address: str, single_sample_id: str = None, mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Initializes this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param single_sample_id: name of a single sample if only this sample should be synced
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        self._species = species
        self._single_sample_id = single_sample_id
        self._uploader_mail_address = uploader_mail_address
        # Parse MongoDB config
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()
        # Parse Bigsdb config
        self._bigsdb_config_data = get_bigsdb_config_data()
        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, \
            self._isolates_resequencing_collection = self._mongoinit.initialise_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()
        self._mongoquerying = Mongoquerying()
        # Open Bigsdb isolates table
        self._isolates_psql_tbl = TblIsolates(self._species)

        # Prepare cgmlst cache updater command
        with TblSchemes(self._species, 'isolates') as isolates_schemes_psql_tbl:
            self._cgmlst_bigsdb_scheme_id = isolates_schemes_psql_tbl.select_scheme_id_cgmlst()[0][0]
        cache_command = f'/home/bigsdb/BIGSdb/scripts/maintenance/update_scheme_caches.pl ' \
                        f'--database bigsdb_{self._species}_isolates --schemes {self._cgmlst_bigsdb_scheme_id} ' \
                        f'--method incremental'
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
            if an insertion into bigsdb fails, the alerts for the succeeded insertions need to be evaluated,
            because else they would not be evaluated at all
            for this purpose the cache first needs to be updated after having inserted new isolates/cgsts
            (the cgst needs to come from the seqdef db)
            """
            traceback1 = traceback.format_exc()

            # todo: disabled following code on 2024/04/08 because isolation date not yet in incoming metadata; to reenable when it does
            # self._cache_command_object.run(Path(os.getcwd()))
            # if self._cache_command_object.returncode != 0:
            #     send_email(f"update of the cache to display the clustering failed on host {socket.gethostname()}")
            #     raise RuntimeError(
            #         f"update of the cache to display the clustering failed on host {socket.gethostname()}")
            #
            # # then run the alerts implementation for distance matrices
            # # ofcourse this can fail too, therefore we encapsulate it in another try except
            # if len(self._list_of_new_isolates_for_alerts + self._list_of_new_versions_for_alerts) > 0 and not \
            #         self._exception_in_alerts:
            #     try:
            #         AlertsToBigs(self._list_of_new_isolates_for_alerts, self._list_of_new_versions_for_alerts,
            #                      self._species, self._cgmlst_bigsdb_scheme_id)
            #     except Exception as exceptionmessage2:
            #         traceback2 = traceback.format_exc()
            #         send_email(f"Failure 1: {exceptionmessage1}\n{traceback1}\n"
            #                    f"Failure 2: {exceptionmessage2}\n{traceback2}",
            #                    subject=f"{Path(__file__).name} double fail on host {socket.gethostname()}")
            #         raise Exception(f"{Path(__file__).name} double fail on host {socket.gethostname()}: "
            #                         f"Failure 1: {exceptionmessage1}\n{traceback1}\n"
            #                         f"Failure 2: {exceptionmessage2}\n{traceback2}")

            send_email(f"{exceptionmessage1}\n{traceback1}")
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: {exceptionmessage1}\n{traceback1}")

    def _mongo_to_bigs(self) -> None:
        """
        Main function
        If the current host is a bigsdb host, syncs all samples (or a single one if provided) with the bigsdb database
        :return: None
        """

        # call the autoexecutable function to insert new alleles and profiles
        NewClusteringInfoToBigs(self._species, Path(self._bigsdb_config_data['naive_clustering_distance_matrix_file'].replace('species', self._species)), mongo_config_data=self._mongo_config_data)

        # update the bigsdb cache so the clustering schemes get updated
        self._cache_command_object.run(Path(os.getcwd()))
        if self._cache_command_object.returncode != 0:
            send_email(f"update of the cache to display the clustering failed on host {socket.gethostname()}")
            raise RuntimeError(f"update of the cache to display the clustering failed on host {socket.gethostname()}")

        # send bad samples from the badqc_isolates collection to BIGSdb
        samples_to_validation_bigs(self._species, mongo_config_data=self._mongo_config_data)

        list_of_documents = self.__get_list_of_documents()

        for document in list_of_documents:
            document_id = document['results']['isolates_id']
            sample_presence = self._isolates_psql_tbl.count_isolate((document_id,))
            if sample_presence[0][0] == 0:
                results_type = "new_isolate"
                self._list_of_new_isolates_for_alerts.append(
                    {'isolate_name': document_id, 'cgST': document['results'].get('cgST'),
                     'isolation_date': document['results']['analysis_date']})  # todo change date to isolation_date
            elif sample_presence[0][0] == 1 and (Path(self._bigsdb_config_data['failsafe']['flag_dir']) / '.'.join(
                    [document_id, self._bigsdb_config_data['failsafe']['flag_append']])).is_file():
                # isolate into bigsdb was started but failed during insertion.
                # if argument "new_isolate" is passed to main_results_inserter and it finds the flag,
                # it will remove the isolate and the flag, and then recreate the flag and start insertion again.
                results_type = "new_isolate"
                self._list_of_new_isolates_for_alerts.append(
                    {'isolate_name': document_id, 'cgST': document['results'].get('cgST'),
                     'isolation_date': document['results']['analysis_date']})  # todo change date to isolation_date
            else:
                results_type = "reanalysis"
                different_version = self.__check_if_reanalysis_different(document, document_id)
                if different_version is False:
                    continue
                self._list_of_new_versions_for_alerts.append({'isolate_name': document_id, 'cgST': document['results'].get('cgST'),
                                                              'isolation_date': document['results']['analysis_date']})

            # continuation of for loop:
            # extract json file to be given to bigs
            if document.get('validation'):
                # add validation metadata to results in order to be able to insert them into BIGSdb
                document['results']['validation'] = document['validation']
            document = self._mongoquerying.revert_typinghitlists_to_dictionaries(document, self._headers_collection)
            jsonfile = Path(f"{mongo_config_data.get('temp_dir')}/{document_id}_temp.json")
            with jsonfile.open('w') as handle:
                handle.write(json.dumps(document['results']))
            MainResultsInserter(document_id, self._uploader_mail_address, self._species, results_type, jsonfilepath=jsonfile, report_access=document['report_directory'])
            jsonfile.unlink()
            fasta_name = Path(document['fasta_path']).name
            fasta_path_remote = Path(document['report_directory']) / 'assembly' / fasta_name
            with tempfile.NamedTemporaryFile(dir=mongo_config_data.get('temp_dir'), mode="w") as temp_fasta:
                temp_fasta_path = Path(mongo_config_data.get('temp_dir')) / temp_fasta.name
                scp_command = f"scp -o StrictHostKeyChecking=no -i /home/bigsdb/.ssh/.id_rsa_reportsapi bigsdb@{mongo_config_data.get('azure_reportsapi_ip')}:{fasta_path_remote} {str(temp_fasta_path)}"
                scp_cmd = Command(scp_command)
                scp_cmd.run(Path(mongo_config_data.get('temp_dir')))
                if scp_cmd.returncode != 0:
                    raise Exception(f"scp command to copy fasta from Azure to onsite failed: {scp_cmd.stderr}\nscp command: {scp_command}")

                if results_type == 'new_isolate':
                    insert_assembly(document_id, self._species, temp_fasta_path)
                elif results_type == 'reanalysis' and document['validation']['type'] == 'resequencing':
                    last_two_validation_dates = self._isolates_psql_tbl.select_validationdate_for_isolate((document_id,))
                    # select to check that the previous version's validation date is different from the current
                    if last_two_validation_dates[0][0] != last_two_validation_dates[1][0]:
                        # revert the changes done in maininserter that move the assembly to the newest version
                        with TblSequenceBin(self._species) as isolates_seqbin_psql_tbl:
                            isolates_seqbin_psql_tbl.revert_sequencebin_newversion([document_id])
                        with TblSeqBinStats(self._species) as isolates_seqbinstats_psql_tbl:
                            isolates_seqbinstats_psql_tbl.revert_seqbinstats_newversion([document_id])
                        insert_assembly(document_id, self._species, temp_fasta_path)
                logging.info(f"wrote new results version for {document_id} to bigsdb")

        # Update cache again before alerts implementation because new isolates won't have cgST's but are needed for alerts implementation
        self._cache_command_object.run(Path(os.getcwd()))
        if self._cache_command_object.returncode != 0:
            send_email(f"update of the cache to display the clustering failed on host {socket.gethostname()}")
            raise RuntimeError(f"update of the cache to display the clustering failed on host {socket.gethostname()}")

        list_of_isolates_in_bigs = self._isolates_psql_tbl.listing_isolates()
        with Path('/scratch/bigsupload/mongo/list_of_isolates.txt').open('w') as fileout:
            for item in list_of_isolates_in_bigs:
                fileout.write(f"{item[0]}\n")

        # Run Alerts to bigs after updating the cache because it accesses a SQL table that is updated by the cache updater.
        # also run it after having inserted all isolates into bigsdb
        # todo: disabled following code on 2024/04/08 because isolation date not yet in incoming metadata; to reenable when it does
        # try:
        #     if len(self._list_of_new_isolates_for_alerts + self._list_of_new_versions_for_alerts) > 0:
        #         AlertsToBigs(self._list_of_new_isolates_for_alerts, self._list_of_new_versions_for_alerts, self._species, self._cgmlst_bigsdb_scheme_id)
        # except:
        #     self._exception_in_alerts = True

    def __get_list_of_documents(self) -> List[Dict[str, Any]]:
        """
        Gets the list of documents, = all if no single_sample_id, else list of single document
        :return: list of documents (dictionaries)
        """
        if self._single_sample_id:
            query_single = self._isolates_collection.find_one({'_id': self._single_sample_id})
            if query_single is not None:
                list_of_documents = [query_single]
            else:
                send_email(f"Can not find document with _id '{self._single_sample_id}' in isolates")
                raise Exception(f"Can not find document with _id '{self._single_sample_id}' in isolates")

        else:
            list_of_documents = list(self._isolates_collection.find())
        return list_of_documents

    def __check_if_reanalysis_different(self, document: Dict[str, Any], document_id: str) -> bool:
        """
        Checks if the reanalysis is different or not, outside this function: continues the for loop,
        it is called in, to the next sample if not different
        :param document: document dictionary
        :param document_id: name of the isolate
        :return: boolean whether version is different or not
        """
        latest_analysis_date_bigs = (self._isolates_psql_tbl.select_latestanalysisdate_for_isolate((document_id,)))[0][
            0]  # this appearently is a datetime object
        with TblEavTextHidden(self._species) as isolates_eavth_psql_tbl:
            mongo_results_changed_version_bigs_query = isolates_eavth_psql_tbl.select_mongo_resultsversion(
                (document_id,))
        # as of 2022/12/22 mongo_results_version in bigs is changed version
        if len(mongo_results_changed_version_bigs_query) == 0:
            # Accounting for old samples that didnt have a version yet
            mongo_results_changed_version_bigs = 1
        else:
            mongo_results_changed_version_bigs = int(mongo_results_changed_version_bigs_query[0][0])
        if convert_dmyhms_to_dateobj(document['results']['analysis_date']) > latest_analysis_date_bigs:
            new_results = document['results']
            if new_results['changed_version'] == int(mongo_results_changed_version_bigs):
                # results are same so do nothing
                logging.info(
                    f"results_version might be different, but changed_version same in mongodb and bigsdb for {document_id}")
                different_version = False
            else:
                different_version = True
        else:
            logging.info(
                f"results version same in mongodb and bigsdb for sample {document_id}")
            different_version = False
        return different_version

    def __exit__(self) -> None:
        """
        Closes the isolates psql table when the class is closed
        :return: None
        """
        self._isolates_psql_tbl.close()


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse Mongo config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    MongoToBigs(args.species, args.uploader_mail_address,
                single_sample_id=(args.single_sample_id if args.single_sample_id else None),
                mongo_config_data=mongo_config_data)
