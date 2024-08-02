import json
import logging
import sys
import tempfile
import yaml
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

import paramiko

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# SFTP connection parameters
hostname = 'sftp.healthdata.be'
port = 2222  # Default SFTP port
username = 'nrc'
password = 'to_be_replaced_by_ansible'


class SendGenomicToDWH:
    """
    Class to get all required values for a pathogen from a MongoDB document and
    to send these values as a JSON file to the DWH over SFTP.
    """
    def __init__(self, document: Dict[str, Any], mongo_config_data: Dict[str, Any], species: str) -> None:
        """
        Initialises this class and executes the main function.
        :param document: MongoDB document for a single sample.
        :param mongo_config_data: the MongoDB configuration file.
        :param species: commonly used bioit species name: either genus or specific like stec.
        :return: None
        """
        self._document = document
        self._mongo_config_data = mongo_config_data
        self._species = species

        # get HD ODS dictionaries to be able to translate to useable text
        with (Path(__file__).resolve().parent / 'config' / 'codes_send_genomic_to_DWH.yml').open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)

        # initialize ssh & sftp
        self._ssh, self._sftp = self._open_sftp_connection()

        self._send_genomic_to_dwh()

        self._close_sftp_connection()

    @staticmethod
    def _open_sftp_connection() -> (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Opens an SSH and SFTP connection using variables defined as constants at the top of this script.
        :return: an ssh and sftp client for further use
        """
        # Create an SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the server
        ssh.connect(hostname, port, username, password)

        # Create an SFTP session
        sftp = ssh.open_sftp()
        return ssh, sftp

    def _send_genomic_to_dwh(self) -> None:
        """
        Main function to send the genomic indicators to the HealthData DataWareHouse.
        :return: None
        """
        output_json_dict = {}
        for variable, list_path in self._translation_codes['common'].items():
            output_json_dict[variable] = self.__access_value(list_path)
        if self._translation_codes.get(self._species):
            for variable, list_path in self._translation_codes[self._species].items():
                output_json_dict[variable] = self.__access_value(list_path)

        with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
            # business key is not allowed to be in the filename according to Sébastien Pendeville
            jsonfile = Path(temp_json_dir) / f"{self._document['pseudo_id']}.json"
            with jsonfile.open('w') as handle:
                handle.write(json.dumps(output_json_dict))

            # Upload the file
            # Created the dev, test, and acc folders manually
            remote_path = f"to_hd/" \
                          f"{self._mongo_config_data['dtap'] + '/' if self._mongo_config_data['dtap'] != 'prod' else ''}" \
                          f"{jsonfile.name}"
            logging.info(output_json_dict) # todo uncomment self._sftp.put(str(jsonfile), remote_path)
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
