import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

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
    def __init__(self, document: Dict[str, Any], mongo_config_data: Dict[str, Any], species: str,
                 alternate_dtap: str = None) -> None:
        """
        Initialises this class and executes the main function.
        :param document: MongoDB document for a single sample.
        :param mongo_config_data: the MongoDB configuration file.
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param alternate_dtap: alternative dtap (should take test or prod from mongo config) in case we want to test dev
        or acc
        :return: None
        """
        super().__init__()

        self._document = document
        self._mongo_config_data = mongo_config_data
        self._species = species
        self._alternate_dtap = alternate_dtap

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
        
        send_dictionary_to_ods(self._output_json_dict, self._sftp, alternate_dtap=self._alternate_dtap)

        self._close_sftp_connection(self._ssh, self._sftp)

    def _create_output_json_dict(self) -> Dict[str, Any]:
        """"
        Finds the required values for the ODS in the document and puts them in a dictionary with the right format.
        :return: output dictionary in the right format ready to be sent to the ODS
        """
        data_dict = {}
        for variable, list_path in self._translation_codes['common'].items():
            data_dict[variable] = access_value_in_dict_using_list_as_dictpath(list_path, self._document)
        # although the DT_PIPELINE_ANAL is common, it can not be processed regularly using
        # the previous function because it needs to be converted
        data_dict['DT_PIPELINE_ANAL'] = datetime.strptime(self._document['results']['analysis_date'],
                                                          '%d/%m/%Y - %X').strftime('%Y-%m-%dT%X')

        if self._translation_codes.get(self._species):
            for variable, list_path in self._translation_codes[self._species].items():
                data_dict[variable] = access_value_in_dict_using_list_as_dictpath(list_path, self._document)
                if 'CD_GENTPE' in variable:
                    if not data_dict[variable]:
                        # The Mykrobe fields are optional
                        data_dict.pop(variable)
                    else:
                        # I have at least noticed one instance where an R was lowercase
                        data_dict[variable] = (data_dict[variable]).upper()
        return {'metadata': {'version': self._translation_codes['pathogens'][self._species]['dcd_version'],
                             'data_collection': self._translation_codes['pathogens'][self._species]['dcd_code'],
                             'dcd_name': self._translation_codes['pathogens'][self._species]['dcd_name']},
                'data': data_dict}

    def __del__(self) -> None:
        """
        Closes the SSH and SFTP clients upon exit.
        :return: None
        """
        self._close_sftp_connection(self._ssh, self._sftp)
