import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.python_utility_functions import access_value_in_dict_using_list_as_dictpath
from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD, CODES_GENOMIC_ODS
from bioit_nrc_integration.python.util.python_utility_functions import send_dictionary_to_ods
from bioit_nrc_integration.python.util.sftp_connection import SFTPConnection

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


class SendGenomicToODS(SFTPConnection):
    """
    Class to get all required values for a pathogen from a MongoDB document and
    to send these values as a JSON file to the ODS over SFTP.
    """
    def __init__(self, document: dict[str, Any], species: str, upload_path: str) -> None:
        """
        Initialises this class and executes the main function.
        :param document: MongoDB document for a single sample.
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param upload_path: The upload path
        :return: None
        """
        super().__init__()

        self._document = document
        self._species = species

        # get HD ODS dictionaries to be able to translate to useable text
        with CODES_GENOMIC_ODS.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)
        # get sftp credentials
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)

        # initialize ssh & sftp
        self._ssh, self._sftp = self._open_sftp_connection(
            self._sftp_credentials_hd['hostname_send_genomic_to_ODS'],
            self._sftp_credentials_hd['port_send_genomic_to_ODS'],
            self._sftp_credentials_hd['username_send_genomic_to_ODS'],
            self._sftp_credentials_hd['password_send_genomic_to_ODS'])

        self._output_json_dict = self._create_output_json_dict()
        
        send_dictionary_to_ods(self._output_json_dict, self._sftp, upload_path)

        self._close_sftp_connection(self._ssh, self._sftp)

    def _create_output_json_dict(self) -> dict[str, Any]:
        """
        Finds the required values for the ODS in the document and puts them in a dictionary with the right format.
        :return: output dictionary in the right format ready to be sent to the ODS
        """
        data_dict = {}
        for variable, variable_info in self._translation_codes['common'].items():
            data_dict[variable] = access_value_in_dict_using_list_as_dictpath(variable_info['dict_path'],
                                                                              self._document)
        # although the DT_PIPELINE_ANAL is common, it can not be processed regularly using
        # the previous function because it needs to be converted
        data_dict['DT_PIPELINE_ANAL'] = datetime.strptime(self._document['results']['analysis_date'],
                                                          '%d/%m/%Y - %X').strftime('%Y-%m-%dT%X')

        if self._translation_codes.get(self._species):
            for variable, variable_info in self._translation_codes[self._species].items():
                data_dict[variable] = access_value_in_dict_using_list_as_dictpath(variable_info['dict_path'],
                                                                                  self._document)
                if variable_info.get('code_list'):
                    data_dict[variable] = self._translation_codes['code_lists'][
                        variable_info['code_list']][data_dict[variable]]
            if self._species == 'influenza':
                self.__add_influenza_a_ha_na_info(data_dict)
        return {'metadata': {'version': self._translation_codes['pathogens'][self._species]['dcd_version'],
                             'data_collection': self._translation_codes['pathogens'][self._species]['dcd_code'],
                             'dcd_name': self._translation_codes['pathogens'][self._species]['dcd_name']},
                'data': data_dict}

    @staticmethod
    def __add_influenza_a_ha_na_info(data_dict: dict[str, Any]) -> None:
        """
        Checks if the pathogen is influenza A, then checks if the Type matches HxNx, and if it does, splits HxNx into Hx
        and Nx and adds these to their corresponding variables in the data dictionary to be sent.
        :param data_dict: the data dictionary to send to the ODS, to be modified in place.
        :return: None
        """
        if data_dict['TX_GENTPE_TPE'] == 'A':
            match = re.match(r"^H(\d+)N(\d+)$", data_dict['TX_GENTPE_SUBTPE'])
            if match:
                data_dict['TX_GENTPE_SUBTPE_HEMAG'] = f"H{match.group(1)}"
                data_dict['TX_GENTPE_SUBTPE_NEURAM'] = f"N{match.group(2)}"

    def __del__(self) -> None:
        """
        Closes the SSH and SFTP clients upon exit.
        :return: None
        """
        self._close_sftp_connection(self._ssh, self._sftp)
