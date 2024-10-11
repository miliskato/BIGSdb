import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Literal

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.maininserter import MainInserter
from bioit_bigsdb_scripts.components.json_typingresultsinserter import JsonTypingResultsInserter
from bioit_bigsdb_scripts.components.json_genedetectionresultsinserter import JsonGeneDetectionResultsInserter
from bioit_bigsdb_scripts.components.psql import TblIsolates, TblAlleleDesignations, TblEavText, TblEavBoolean, \
    TblEavInt
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_mongodb_scripts.model.json_model import JsonReportDict, ResultType
from bioit_mongodb_scripts.util.python_utility_functions import send_email


class MainResultsInserter:
    def __init__(self, isolatename: str, uploader_mail_address: str, species: str, results_type: ResultType, report_access: str, vcf_path: str, mongo_dtap: str,
                 json_results: JsonReportDict, naive_clustering_distance_matrix_file: Path) -> None:
        """
        Initialises the class and runs the main function.
        See also argparse function for variables and their requiredness.
        :param isolatename: name of the isolate
        :param uploader_mail_address: mailadress of the uploader
        :param species: commonly used bioit species name: either genus or specific like stec
        :param results_type: either 'new_isolate','badqc','resequencing','reanalysis'
        :param report_access: report_directory from MongoDB
        :param vcf_path: subdirectory containing the vcf file
        :param mongo_dtap: dtap from mongo config
        :param json_results: results for the isolate
        :param naive_clustering_distance_matrix_file: The path to the naive clustering cgmlst distance matrix file
        :return: None
        """
        # Input parameters
        self._isolatename = isolatename
        self._uploader_mail_address = uploader_mail_address
        self._species = species
        self._results_type = results_type
        self._report_access = report_access
        self._vcf_path = vcf_path
        self._mongo_dtap = mongo_dtap
        self._json_report = json_results
        self._naive_clustering_distance_matrix_file = naive_clustering_distance_matrix_file

        self._bigsdb_config_data = get_bigsdb_config_data()

        # Execute main function
        try:
            self._main_results_inserter()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            raise Exception(f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            
    def _main_results_inserter(self) -> None:
        """
        Main function, inserts isolate and its results into BIGSdb.
        :return: None
        """
        # fail safe mechanism is initated before inserting the isolate
        # fail safe mechanism uses a flagfile to lock the isolate insertion and checks whether the previous insertion of the isolate succeeded.
        with TblIsolates(self._species) as isolates_psql_tbl:
            self.__fail_safe_mechanism(isolates_psql_tbl)

        maininserter = MainInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data,
                                    self._report_access, self._vcf_path, self._mongo_dtap,
                                    self._naive_clustering_distance_matrix_file)
        if self._results_type == 'new_isolate' or self._results_type == 'badqc':
            maininserter.insert_new_isolate(self._uploader_mail_address)
        elif self._results_type == 'reanalysis' or self._results_type == 'resequencing':
            self._handle_reanalysis_and_reseq()
            maininserter.update_isolate_analysis_date()
        maininserter.insert_main_metadata()

        JsonTypingResultsInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data, self._report_access).insert_typing_results()
        JsonGeneDetectionResultsInserter(self._isolatename, self._species, self._json_report, self._bigsdb_config_data, self._report_access).insert_genedetection_results()
        logging.info('Finished inserting results')
        self.__delete_flagfile()

    def ___make_flagfilepath(self) -> Path:
        """
        Returns the flag file path
        :return: flag file path
        """
        return Path(self._bigsdb_config_data['failsafe']['flag_dir']) / '.'.join([self._isolatename, self._bigsdb_config_data['failsafe']['flag_append']])

    def __fail_safe_mechanism(self, isolates_psql_tbl: TblIsolates) -> None:
        """
        Creates a flagfile if insertion is started and no flagfile is present.
        else insertion is started and flag file is present: remove highest version of sample and
         reinsert if multiple versions, if only one version, sample is reinserted in the main workflow below
        :param isolates_psql_tbl: isolates db isolates table/ connection instance for a given species
        :return: None
        """
        try:
            if not Path(self._bigsdb_config_data['failsafe']['flag_dir']).is_dir():
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).mkdir(parents=True, exist_ok=True)
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).chmod(0o755)
            flagfilepath = self.___make_flagfilepath()
            if flagfilepath.is_file():
                logging.warning(
                    f"fail safe mechanism detects that the bigsdb insertion for sample {self._isolatename} was started but did not finish. Removing {self._isolatename} from Bigsdb to be able to restart inserting.")
                isolates_psql_tbl.delete_isolate([self._isolatename])
            else:
                flagfilepath.touch()
                flagfilepath.chmod(0o755)
                logging.info(f"flagfilepath {flagfilepath}")
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")

    def __delete_flagfile(self) -> None:
        """
        :return: None, Removes flagfile
        """
        flagfilepath: Path = self.___make_flagfilepath()
        try:
            flagfilepath.unlink()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")

    def _handle_reanalysis_and_reseq(self) -> None:
        """
        Remove previously inserted data for this isolate in the db including eav text, eav bool, allele designation,
        This should avoid error from postgres while reinserting new version of these results
        """
        if self._results_type == 'reanalysis ' or self._results_type == 'resequencing':
            with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl, TblEavText(
                    self._species) as isolates_eavt_psql_tbl, TblEavBoolean(self._species) as isolates_eavb_psql_tbl, \
                    TblEavInt(self._species) as isolates_eavi_psql_tbl:
                isolates_ad_psql_tbl.delete_all_designations_of_isolate((self._isolatename,))
                isolates_eavt_psql_tbl.delete_all_eav_by_isolate_id((self._isolatename,))
                isolates_eavb_psql_tbl.delete_eavbool_for_isolate((self._isolatename,))
                isolates_eavi_psql_tbl.delete_eav_int_for_isolate((self._isolatename,))
