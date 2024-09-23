import json
import logging
import sys
import tempfile
import yaml
from pathlib import Path
from typing import Any, Dict

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))


# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD, CODES_GENOMIC_DWH
from bioit_nrc_integration.python.util.sftp_connection import SFTPConnection


class SendMappingTableToODS(SFTPConnection):
    """
    Class to convert a mapping table to HD variables and to send this converted table as a
    JSON file to the ODS over SFTP.
    """
    def __init__(self, mapping_table: Dict[str, str], species: str, alternate_dtap: str = None) -> None:
        """
        Initialises this class and executes the main function.
        :param mapping_table: MongoDB document originating from the local mapping table collection.
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param alternate_dtap: alternative dtap (should take test or prod from mongo config) in case we want to test dev or acc
        :return: None
        """
        super().__init__()

        self._mapping_table = mapping_table
        self._species = species
        self._alternate_dtap = alternate_dtap

        # get sftp credentials
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)
        with CODES_GENOMIC_DWH.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)

        # initialize ssh & sftp
        self._ssh, self._sftp = self._open_sftp_connection(
            self._sftp_credentials_hd['hostname_send_mapping_table_to_ODS'],
            self._sftp_credentials_hd['port_send_mapping_table_to_ODS'],
            self._sftp_credentials_hd['username_send_mapping_table_to_ODS'],
            self._sftp_credentials_hd['password_send_mapping_table_to_ODS'])

        self._mapping_table_with_healthdata_names = self._create_mapping_table_with_healthdata_names()

        self._send_mapping_table_to_ods()

        # Close the SFTP session
        self._close_sftp_connection(self._ssh, self._sftp)

    def _create_mapping_table_with_healthdata_names(self) -> Dict[str, Any]:
        """
        Creates the mapping table for the ODS in the requested format.
        :return: mapping table ready to be sent to the ODS
        """
        return {'data': {'TX_SAMPLE_ID ': self._mapping_table['_id'],
                         'TX_BIOIT_TECHNICAL_ID': self._mapping_table['pseudo_id'],
                         'TX_BUSINESS_KEY': self._mapping_table['TX_BUSINESS_KEY']},
                'metadata': {'version': self._translation_codes['pathogens'][self._species]['dcd_version'],
                             'data_collection': self._translation_codes['pathogens'][self._species]['dcd_code'],
                             'dcd_name': self._translation_codes['pathogens'][self._species]['dcd_name']
                             }
                }

    def _send_mapping_table_to_ods(self) -> None:
        """
        Sends the mapping table to the ODS
        :return: None
        """
        with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
            # business key is not allowed to be in the filename according to Sébastien Pendeville
            jsonfile = Path(temp_json_dir) / f"{self._mapping_table['pseudo_id']}.json"
            with jsonfile.open('w') as handle:
                handle.write(json.dumps(self._mapping_table_with_healthdata_names))

            # Upload the file
            remote_path = f"upload/{(self._alternate_dtap + '/') if self._alternate_dtap else ''}{jsonfile.name}"
            self._sftp.put(str(jsonfile), remote_path)
            logging.info(f"File uploaded successfully to {remote_path}")

    def __del__(self) -> None:
        """
        Closes the SSH and SFTP clients upon exit.
        :return: None
        """
        self._close_sftp_connection(self._ssh, self._sftp)
