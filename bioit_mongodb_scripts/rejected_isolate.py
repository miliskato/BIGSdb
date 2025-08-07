import logging
import sys
import tempfile
from pathlib import Path
from typing import Tuple

import psycopg

from bioit_bigsdb_scripts.components.psql.psql_tbl_rejected_isolates import TblRejectedIsolates
from bioit_bigsdb_scripts.utils.url_helper import UrlHelper
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.model.json_model import JsonReportDict
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation


class RejectedIsolate:
    """
    Class to insert a rejected isolate in BIGSdb.
    """

    def __init__(self, species: str, isolate_id: str, pseudo_id: str, mongo_config_provider: MongoConfigProvider) -> None:
        """
        Initializes this class.
        :param species: Commonly used bioit species name: either genus or specific like stec
        :param isolate_id: Isolate ID
        :param pseudo_id: Pseudo ID
        :param mongo_config_provider: the mongodb configuration provider
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

        self._species = species
        self._isolate_id = isolate_id
        self._pseudo_id = pseudo_id
        self._mongo_config_provider = mongo_config_provider

        # Open collection Atlas MongoDB
        self._mongoinit = MongoInitialisation(self._species,self._mongo_config_provider.get_azure_connection_string(self._species),self._mongo_config_provider.dtap)
        self._rejected_isolates_collection = self._mongoinit.initialise_isolates_rejected_coreqc_collection()

        # Open collection local MongoDB
        self._mongoinit_local = MongoInitialisation(self._species,self._mongo_config_provider.get_local_connection_string(self._species),self._mongo_config_provider.dtap)

        self._rejected_isolate_document = self._get_rejected_isolate_document()

    def _get_rejected_isolate_document(self) -> dict:
        """
        Returns the MongoDB document of the rejected isolate.
        :return: MongoDB rejected isolate document (dictionary)
        """
        document = self._rejected_isolates_collection.find_one({'_id': self._pseudo_id})
        return document

    def insert_in_rejected_isolates_table(self) -> None:
        """
        Inserts the rejected isolate into the rejected isolates table in BIGSdb.
        :return: None
        """
        with TblRejectedIsolates(self._species) as rejected_isolates_psql_tbl:
            isolate_exists = rejected_isolates_psql_tbl.exists_isolate((self._isolate_id,))
            if isolate_exists[0][0]:
                rejected_isolates_psql_tbl.delete_isolate((self._isolate_id,))
            insertion_date, insertion_type, rejection_reasons, report_link = self._retrieve_fields(rejected_isolates_psql_tbl)
            rejected_isolates_psql_tbl.insert_isolate(
                (self._isolate_id, insertion_date, rejection_reasons, insertion_type, report_link))
            self._update_mongodb()
        if insertion_type != 'manual':
            self._export_json_report()

    def _retrieve_fields(self, rejected_isolates_psql_tbl: psycopg.connection) -> Tuple[str, str, str, str]:
        """
        Retrieves the necessary fields from the rejected isolate document to insert in BIGSdb.
        :param rejected_isolates_psql_tbl: Connection to the rejected isolates psql table
        :return: insertion date, insertion type, rejection reasons and report link
        """
        insertion_date = str(self._rejected_isolate_document['creation_date'])
        insertion_type = str(self._rejected_isolate_document['insertion_type'])
        if insertion_type == 'manual':
            rejection_reasons = self._rejected_isolate_document['rejection_reasons']['manual']
            report_link = 'unavailable'
        else:
            rejection_reasons = ', '.join(
                qc_metric['reason'] for qc_metric in self._rejected_isolate_document['rejection_reasons'].values())
            rejected_isolate_id = str(rejected_isolates_psql_tbl.select_last_rejected_isolate_id() + 1)
            report_url = UrlHelper.report_for_validation_rejected_isolate_id(
                self._species, self._pseudo_id, rejected_isolate_id, insertion_date, 'rejected_isolate')
            report_link = f'<a href="{report_url}" target = "_blank"> report </a>'
        return insertion_date, insertion_type, rejection_reasons, report_link

    def _update_mongodb(self) -> None:
        """
        Inserts an extra field inserted_in_bigsdb in MongoDB for the rejected isolate.
        :return: None
        """
        self._rejected_isolates_collection.update_one({'_id': self._pseudo_id}, {'$set': {'inserted_in_bigsdb': True}})

    def _export_json_report(self) -> None:
        """
        Exports the JSON report to the report directory.
        :return: None
        """
        json_path_remote = Path(self._rejected_isolate_document['report_directory']) / 'report.json'
        with tempfile.NamedTemporaryFile(dir=self._mongo_config_provider.temp_dir) as temp_json:
            scp_command = f"scp -o StrictHostKeyChecking=no -i /home/bigsdb/.ssh/.id_rsa_reportsapi bigsdb@{self._mongo_config_provider.azure_reportsapi_ip}:{json_path_remote} {temp_json.name}"
            scp_cmd = Command(scp_command)
            scp_cmd.run(Path(self._mongo_config_provider.temp_dir))
            if scp_cmd.returncode != 0:
                raise Exception(
                    f"scp command to copy JSON report from Azure to onsite failed: {scp_cmd.stderr}\nscp command: {scp_command}")
            json_file = JsonReportDict.from_json(Path(temp_json.name))
            json_file['sample'] = json_file['sample'].replace(self._pseudo_id, self._isolate_id)
            json_file['input_files'] = json_file['input_files'].replace(self._pseudo_id, self._isolate_id)
            path = Path(self._mongo_config_provider.json_reports_dir) / 'coreqc_rejected' / f'{self._isolate_id}.json'
            json_file.dump_to_json_file(path)
