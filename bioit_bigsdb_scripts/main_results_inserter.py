import logging
import socket
import sys
import tempfile
import traceback
from pathlib import Path

from pymongo.collection import Collection
from psycopg.types.json import Jsonb

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.maininserter import MainInserter
from bioit_bigsdb_scripts.components.json_typingresultsinserter import JsonTypingResultsInserter
from bioit_bigsdb_scripts.components.json_genedetectionresultsinserter import JsonGeneDetectionResultsInserter
from bioit_bigsdb_scripts.components.psql import TblAlleleDesignations, TblEavText, TblAnalysisResults
from bioit_mongodb_scripts.model.json_model import JsonReportDict, ResultType
from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_bigsdb_scripts.insert_assembly import insert_assembly
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider


class MainResultsInserter:
    """
    Class to insert the isolate and associated genomic indicator/metadata into BIGSdb databases
    """

    def __init__(self, isolatename: str, uploader_mail_address: str, species: str, results_type: ResultType,
                 report_access: str, vcf_path: str, fasta_path: str, viral_species: bool,
                 json_results: JsonReportDict, isolation_date: str,
                 nominative_labtest_clinical_metadata_collection: Collection) -> None:
        """
        Initialises the class and runs the main function.
        See also argparse function for variables and their requiredness.

        :param uploader_mail_address: mailadress of the uploader
        :param species: commonly used bioit species name: either genus or specific like stec
        :param results_type: either 'new_isolate', 'goodqc', 'warningqc', 'resequencing', 'reanalysis'
        :param report_access: report_directory from MongoDB
        :param vcf_path: subdirectory containing the vcf file
        :param fasta_path: subdirectory containing the fasta file
        :param viral_species: True if species is viral, False if species is bacterial
        :param json_results: results for the isolate
        :param isolation_date: isolation date as str as DD/MM/YYYY
        :return: None
        """
        # Input parameters
        self._isolatename = isolatename
        self._uploader_mail_address = uploader_mail_address
        self._species = species
        self._results_type = results_type
        self._report_access = report_access
        self._vcf_path = vcf_path
        self._fasta_path = fasta_path
        self._viral_species = viral_species
        self._json_report = json_results
        self._isolation_date = isolation_date
        self._nominative_labtest_clinical_metadata_collection = nominative_labtest_clinical_metadata_collection
        self._mongo_config_provider = MongoConfigProvider()

        self._bigsdb_config_data = get_bigsdb_config_data()

        # Execute main function
        try:
            self._main_results_inserter()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            raise Exception(
                f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')

    def _main_results_inserter(self) -> None:
        """
        Main function, inserts isolate and its results into BIGSdb.
        :return: None
        """
        # fail safe mechanism is initated before inserting the isolate
        # fail safe mechanism uses a flagfile to lock the isolate insertion and checks whether the previous insertion of the isolate succeeded.

        maininserter = MainInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data,
                                    self._report_access, self._vcf_path, self._viral_species)
        if self._results_type == 'new_isolate' or self._results_type == 'warningqc' or self._results_type == 'goodqc':
            maininserter.insert_new_isolate(self._uploader_mail_address, self._isolation_date)
        elif self._results_type == 'reanalysis' or self._results_type == 'resequencing':
            self._handle_reanalysis_and_reseq()
            maininserter.update_isolate_analysis_date()
        self.__insert_assembly_into_bigs()

        JsonTypingResultsInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data,
                                  self._report_access).insert_typing_results()
        JsonGeneDetectionResultsInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data,
                                         self._report_access).insert_genedetection_results()
        self._insert_clustering_results(self._json_report)
        logging.info('Finished inserting results')

    def _handle_reanalysis_and_reseq(self) -> None:
        """
        Remove previously inserted data for this isolate in the db including eav text, eav bool, allele designation,
        This should avoid errors from postgres while reinserting new version of these results
        :return: None
        """
        if self._results_type == 'reanalysis' or self._results_type == 'resequencing':
            with (TblAlleleDesignations(self._species) as isolates_ad_psql_tbl, TblEavText(self._species) as isolates_eavt_psql_tbl,
                  TblAnalysisResults(self._species) as isolates_ana_res_psql_tbl):
                isolates_ad_psql_tbl.delete_all_designations_of_isolate((self._isolatename,))
                isolates_eavt_psql_tbl.delete_all_eav_of_isolate((self._isolatename,))
                isolates_ana_res_psql_tbl.delete_analysis_results_isolate_name((self._isolatename,))
            self._nominative_labtest_clinical_metadata_collection.update_one({'_id': self._isolatename},
                                                                             {'$set': {'inserted_into_bigsdb': False}})

    def __insert_assembly_into_bigs(self) -> None:
        """
        Fetches the assembly from Azure and inserts into bigsdb when applicable
        :return: None
        """
        # In case of an actual reanalysis, the MainResultsInserter handles the assembly transfer between
        # isolates and we do not want to scp the assembly from Azure
        if self._results_type == 'reanalysis':
            return
        fasta_path_remote = self._fasta_path
        temp_dir = self._mongo_config_provider.temp_dir
        with tempfile.NamedTemporaryFile(dir=temp_dir, mode="w") as temp_fasta:
            temp_fasta_path = Path(temp_dir) / temp_fasta.name
            scp_command = f"scp -o StrictHostKeyChecking=no -i /home/bigsdb/.ssh/.id_rsa_reportsapi bigsdb@{self._mongo_config_provider.azure_reportsapi_ip}:{fasta_path_remote} {str(temp_fasta_path)}"
            scp_cmd = Command(scp_command)
            scp_cmd.run(Path(temp_dir))
            if scp_cmd.returncode != 0:
                raise Exception(
                    f"scp command to copy fasta from Azure to onsite failed: {scp_cmd.stderr}\nscp command: {scp_command}")

            insert_assembly(self._isolatename, self._species, temp_fasta_path, self._results_type)
            logging.info(f"Inserted assembly for isolate {self._isolatename} into bigsdb")

            # The resequencing is for now disable as also commented in sample_to_validation_bigs.py
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

    def _insert_clustering_results(self, json_report: JsonReportDict) -> None:
        """
        Inserts the cgST clustering javascript link for the isolate into the analysis_results table
        :param json_report: json report dict
        :return: None
        """
        isolate_cgst = json_report.get('cgST')
        if isolate_cgst is None:
            return
        with TblAnalysisResults(self._species) as isolates_ana_res_psql_tbl:
            js_link_of_the_cgst = isolates_ana_res_psql_tbl.extract_results_filtered_on_name((isolate_cgst,))
            if js_link_of_the_cgst is not None:
                isolates_ana_res_psql_tbl.insert_analysis_results_isolate_name(('cgST_clustering_on_allelic_dist', self._isolatename, Jsonb(js_link_of_the_cgst)))
