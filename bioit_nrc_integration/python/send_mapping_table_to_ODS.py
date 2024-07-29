import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict

import paramiko

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# SFTP connection parameters
hostname = 'hera-dc.healthdata.be'
port = 2222  # Default SFTP port
username = 'to_be_replaced_by_ansible'
password = 'to_be_replaced_by_ansible'


class SendMappingTableToODS:
    """
    Class to convert a mapping table to HD variables and to send this converted table as a
    JSON file to the ODS over SFTP.
    """
    def __init__(self, mapping_table: Dict[str, str]) -> None:
        """
        Initialises this class and executes the main function.
        :return: None
        """
        self._mapping_table = mapping_table
        # initialize ssh & sftp
        self._ssh, self._sftp = self._open_sftp_connection()

        mapping_table_healthdata_names = {'TX_BUSINESS_KEY ': self._mapping_table['_id'],
                                          'TX_BIOIT_TECHNICAL_ID': self._mapping_table['pseudo_id']}
        with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
            # business key is not allowed to be in the filename according to Sébastien Pendeville
            jsonfile = Path(temp_json_dir) / f"{self._mapping_table['pseudo_id']}.json"
            with jsonfile.open('w') as handle:
                handle.write(json.dumps(mapping_table_healthdata_names))

            # Upload the file
            remote_path = f'upload/{jsonfile.name}'
            logging.info(mapping_table_healthdata_names) # todo uncomment self._sftp.put(str(jsonfile), remote_path)
            logging.info(f"File uploaded successfully to {remote_path}")

            # Close the SFTP session
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
