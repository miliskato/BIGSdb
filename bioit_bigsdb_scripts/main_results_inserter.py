import logging
import socket
import sys
import traceback
from pathlib import Path

from pymongo.collection import Collection

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.maininserter import MainInserter
from bioit_bigsdb_scripts.components.json_typingresultsinserter import JsonTypingResultsInserter
from bioit_bigsdb_scripts.components.json_genedetectionresultsinserter import JsonGeneDetectionResultsInserter
from bioit_bigsdb_scripts.components.psql import TblAlleleDesignations, TblEavFloat, TblEavText, TblEavBoolean, \
    TblEavInt, TblEavTextHidden
from bioit_mongodb_scripts.model.json_model import JsonReportDict, ResultType
from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data, send_email


class MainResultsInserter:
    """
    Class to insert the isolate and associated genomic indicator/metadata into BIGSdb databases
    """

    def __init__(self, isolatename: str, uploader_mail_address: str, species: str, results_type: ResultType,
                 report_access: str, vcf_path: str, viral_species: bool,
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
        self._viral_species = viral_species
        self._json_report = json_results
        self._isolation_date = isolation_date
        self._nominative_labtest_clinical_metadata_collection = nominative_labtest_clinical_metadata_collection

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

        JsonTypingResultsInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data,
                                  self._report_access).insert_typing_results()
        JsonGeneDetectionResultsInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data,
                                         self._report_access).insert_genedetection_results()
        logging.info('Finished inserting results')

    def _handle_reanalysis_and_reseq(self) -> None:
        """
        Remove previously inserted data for this isolate in the db including eav text, eav bool, allele designation,
        This should avoid errors from postgres while reinserting new version of these results
        :return: None
        """
        if self._results_type == 'reanalysis' or self._results_type == 'resequencing':
            with (TblAlleleDesignations(self._species) as isolates_ad_psql_tbl, TblEavText(self._species) as isolates_eavt_psql_tbl,
                  TblEavBoolean(self._species) as isolates_eavb_psql_tbl, TblEavInt(self._species) as isolates_eavi_psql_tbl, TblEavFloat(self._species) as isolates_eavfl_psql_tbl):
                isolates_ad_psql_tbl.delete_all_designations_of_isolate((self._isolatename,))
                isolates_eavt_psql_tbl.delete_all_eav_of_isolate((self._isolatename,))
                isolates_eavb_psql_tbl.delete_eavbool_for_isolate((self._isolatename,))
                isolates_eavi_psql_tbl.delete_eav_int_for_isolate((self._isolatename,))
                isolates_eavfl_psql_tbl.delete_eav_float_for_isolate((self._isolatename,))
            with TblEavTextHidden(self._species) as isolates_eavt_hidden_psql_tbl:
                isolates_eavt_hidden_psql_tbl.delete_eavt_hidden((self._isolatename,))
            self._nominative_labtest_clinical_metadata_collection.update_one({'_id': self._isolatename},
                                                                             {'$set': {'inserted_into_bigsdb': False}})
