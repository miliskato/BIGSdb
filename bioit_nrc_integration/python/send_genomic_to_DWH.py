import json
import logging
import sys
import tempfile
import yaml
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import paramiko

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD, CODES_GENOMIC_DWH

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


class SendGenomicToDWH:
    """
    Class to get all required values for a pathogen from a MongoDB document and
    to send these values as a JSON file to the DWH over SFTP.
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
        self._document = document
        self._mongo_config_data = mongo_config_data
        self._species = species
        self._alternate_dtap = alternate_dtap

        # get HD ODS dictionaries to be able to translate to useable text
        with CODES_GENOMIC_DWH.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)
        # get sftp credentials
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)

        # initialize ssh & sftp
        self._ssh, self._sftp = self._open_sftp_connection()

        self._send_genomic_to_dwh()

        self._close_sftp_connection()

    def _open_sftp_connection(self) -> (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Opens an SSH and SFTP connection using variables defined in the sftp credentials configuration file.
        :return: an ssh and sftp client for further use
        """
        # Create an SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the server
        ssh.connect(self._sftp_credentials_hd['hostname_send_genomic_to_DWH'], 
                    self._sftp_credentials_hd['port_send_genomic_to_DWH'], 
                    self._sftp_credentials_hd['username_send_genomic_to_DWH'], 
                    self._sftp_credentials_hd['password_send_genomic_to_DWH'])

        # Create an SFTP session
        sftp = ssh.open_sftp()
        return ssh, sftp

    def _send_genomic_to_dwh(self) -> None:
        """
        Main function to send the genomic indicators to the HealthData DataWareHouse.
        :return: None
        """
        data_dict = {}
        for variable, list_path in self._translation_codes['common'].items():
            data_dict[variable] = self.__access_value(list_path)
        # although the DT_PIPELINE_ANAL is common, it can not be processed regularly using
        # the previous function because it needs to be converted
        data_dict['DT_PIPELINE_ANAL'] = datetime.strptime(self._document['results']['analysis_date'],
                                                          '%d/%m/%Y - %X').strftime('%Y-%m-%dT%X')

        if self._translation_codes.get(self._species):
            for variable, list_path in self._translation_codes[self._species].items():
                data_dict[variable] = self.__access_value(list_path)
                if 'CD_GENTPE' in variable:
                    # I have at least noticed one instance where an R was lowercase
                    data_dict[variable] = (data_dict[variable]).upper()
        output_json_dict = {'metadata': {'version': self._translation_codes['pathogens'][self._species]['dcd_version'],
                                         'data_collection': self._translation_codes['pathogens'][self._species]['dcd_code'],
                                         'dcd_name': self._translation_codes['pathogens'][self._species]['dcd_name']},
                            'data': data_dict}
        with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
            # business key is not allowed to be in the filename according to Sébastien Pendeville
            jsonfile = Path(temp_json_dir) / f"{self._document['pseudo_id']}.json"
            with jsonfile.open('w') as handle:
                handle.write(json.dumps(output_json_dict))

            # Upload the file
            # Created the dev, test, and acc folders manually
            remote_path = f"to_hd/" \
                          f"{self._alternate_dtap + '/' if self._alternate_dtap else self._mongo_config_data['dtap'] + '/' if self._mongo_config_data['dtap'] != 'prod' else ''}" \
                          f"{jsonfile.name}"
            self._sftp.put(str(jsonfile), remote_path)
            logging.info(f"File uploaded successfully to {remote_path}")

    def __access_value(self, dict_path: List) -> str:
        """
        Given a dictionary path as a list, gets the value of this dictionary path from the input document.
        :param dict_path: ordered list of the path in the dictionary
        :return: str
        """
        current = deepcopy(self._document)
        for key in dict_path:
            current = current.get(key)
            if not current:
                break
        return current

    def _close_sftp_connection(self) -> None:
        """
        Closes the SSH and SFTP clients created by _open_sftp_connection.
        :return: None
        """
        self._sftp.close()
        self._ssh.close()

    def __exit__(self) -> None:
        """
        Closes the SSH and SFTP clients upon exit.
        :return: None
        """
        self._close_sftp_connection()
