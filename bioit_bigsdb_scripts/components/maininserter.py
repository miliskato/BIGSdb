import dataclasses
import datetime
import logging
import socket
from typing import Any, Dict

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from .json_superclass import JsonSuperClass
from .psql import TblEavBoolean, TblEavFields, TblEavInt, TblEavText, TblHistory, TblIsolates
from ..utils.html_tbl_templates import HtmlAntiviralAssociationsTableBuilder, HtmlAntiviralMutationsTableBuilder, HtmlRefSelectionTableBuilder, HtmlReportBuilder, HtmlSnpLineageTableBuilder
from ..utils.url_helper import UrlHelper


@dataclasses.dataclass
class MainInserterContext:
    """
    Class used to keep the value of the isolate_id and the report url which are defined in the context of the main class.
    Called when these values are already defined to replace the inheritance, which is not possible for variables defined by a method of the class.
    """
    isolate_id: str
    report_url: str


class MainInserter(JsonSuperClass):
    """
    Class containing definitions used to insert metadata results for both json and tsv input
    """

    def __init__(self, isolatename: str, species: str, json_report_dict: JsonReportDict, config_data: Dict[str, Any],
                 report_access: str, vcf_path: str, viral_species: bool) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param json_report_dict: results of sample
        :param report_access: report_directory from MongoDB
        :param vcf_path: subdirectory containing the vcf file
        :param viral_species: True if species is viral, False if species is bacterial
        :return: None
        """
        super().__init__(isolatename, species, json_report_dict, config_data)
        self._report_access = report_access
        self._vcf_path = vcf_path
        self._viral_species = viral_species

    def insert_new_isolate(self, uploader_mail_address: str, isolation_date: str) -> None:
        """
        main function to insert a new isolate, but only the isolate
        :param uploader_mail_address: mailadress of the uploader of the new isolate
        :param isolation_date: isolation date as str as DD/MM/YYYY
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            sample_presence = isolates_psql_tbl.count_isolate((self._isolatename,))
            if sample_presence[0][0] == 0:
                isolates_psql_tbl.insert_isolate((self._isolatename, uploader_mail_address,  # todo should uploader mail address not removed?
                                                  datetime.datetime.strptime(self._json_report_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'),
                                                  datetime.datetime.strptime(isolation_date, '%d/%m/%Y').strftime('%Y-%m-%d')))
            else:
                raise RuntimeError(f"isolatename {self._isolatename} of {self._species} already exists on host {socket.gethostname()}")
        with TblHistory(self._species) as isolates_history_psql_tbl:
            isolates_history_psql_tbl.insert_history_isolate((self._isolatename, 'Isolate record added'))
        self.__insert_main_metadata()

    def update_isolate_analysis_date(self) -> None:
        """
        Insert a new isolate version for an existing isolate
        :return: None
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            isolates_psql_tbl.update_isolate_analysis_date(
                (datetime.datetime.strptime(self._json_report_dict['analysis_date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'), self._isolatename))
        self.__insert_main_metadata()

    def __create_context(self) -> MainInserterContext:
        """
        Method which is used to return the MainInserterContext object. By essence, private, as this one cannot be used outside the context of the class.
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            isolate_tuple = isolates_psql_tbl.select_id_for_isolate((self._isolatename,))
            isolate_id = str(isolate_tuple[0][0])
        return MainInserterContext(isolate_id, UrlHelper.report_for_isolate(self._species, isolate_id))

    def __insert_main_metadata(self) -> None:
        """
        Inserts the main metadata into bigsdb for an isolate
        :return: None
        """

        context = self.__create_context()

        with TblEavText(self._species) as self._isolates_eavt_psql_tbl, \
                TblIsolates(self._species) as self.isolates_psql_tbl, TblEavInt(self._species) as self._isolates_eavi_psql_tbl:

            pipeline = f'{self._json_report_dict.get("pipeline_name")} {self._json_report_dict.get("pipeline_version")} - {self._json_report_dict.get("input_type")}'
            if not self._viral_species:
                self.isolates_psql_tbl.update_isolate_html_assembly_pipeline(
                    (str(context.isolate_id), str(context.isolate_id), pipeline, self._isolatename))
                self.__update_coverage_info()
            else:
                ref_selection_database = self._json_report_dict['ref_selection'].get('ref_selection_database')
                self.isolates_psql_tbl.update_isolate_html_consensus_pipeline_db(
                    (str(context.isolate_id), str(context.isolate_id), pipeline, ref_selection_database,
                     self._isolatename)
                )
            if 'changed_version' in self._json_report_dict:
                self.isolates_psql_tbl.update_mongo_results_version((self._json_report_dict['changed_version'], str(context.isolate_id)))
            if 'validation' in self._json_report_dict:
                self.isolates_psql_tbl.add_validation((self._json_report_dict['validation']['type'], self._json_report_dict['validation']['curator'],
                                                       datetime.datetime.strptime(self._json_report_dict['validation']['date'], '%d/%m/%Y - %X').strftime('%Y-%m-%d'),
                                                       str(context.isolate_id)))
            logging.info('Metadata insertion successful')

    def __update_coverage_info(self) -> None:
        """
        Updates the coverage info for an isolate.
        :return: None
        """
        if self._json_report_dict['input_type'] != 'fasta':
            coverage_assembly = self._json_report_dict['quast'].get('assembly_avg_coverage', '-')
            coverage_reference = self._json_report_dict['quast'].get('assembly_avg_coverage_ref', '-')
            positions_covered_1x_assembly = self._json_report_dict['quast'].get('assembly_positions_covered_1x', '-')
            positions_covered_1x_reference = self._json_report_dict['quast'].get('assembly_positions_covered_1x_ref', '-')
            self.isolates_psql_tbl.update_coverage_info((coverage_assembly, coverage_reference,
                                                         positions_covered_1x_assembly, positions_covered_1x_reference,
                                                         self._isolatename))
