import sys
from pathlib import Path
from typing import Literal

import paramiko
import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.utils.literal_helper import validate_literal
from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD

SFTPValues = Literal['get', 'send']
SFTPValue = str | SFTPValues  # workaround to avoid pycharm warnings

class SFTPConnectionODS:
    """
    Base Class containing functions to handle an SFTP connection.
    """
    def __init__(self, get_or_send: SFTPValue) -> None:
        """
        Initializes this class and opens an SFTP connection a chosen location.
        :param get_or_send: open a connection to either the getting or the sending SFTP location
        :return: None
        """
        validate_literal(get_or_send, SFTPValues)
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)
        if get_or_send == 'get':
            self._ssh, self.sftp = self._open_sftp_connection_get_nominative_from_ods()
        else:  # if get_or_send == 'send':
            self._ssh, self.sftp = self._open_sftp_connection_send_genomic_to_ods()

    @staticmethod
    def __open_sftp_connection(hostname: str, port: str | int, username: str, password: str) -> \
            (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Opens an SSH and SFTP connection using variables defined in the sftp credentials configuration file.
        :param hostname: sftp hostname
        :param port: sftp port
        :param username: sftp username
        :param password: sftp password
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

    def close_sftp_connection(self) -> None:
        """
        Closes the SSH and SFTP clients created by open_sftp_connection.
        :return: None
        """
        self.sftp.close()
        self._ssh.close()

    def _open_sftp_connection_get_nominative_from_ods(self) -> (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Public function to open an SFTP connection to the location where nominative files are deposited by the ODS.
        :return: an ssh and sftp client for further use
        """
        return self.__open_sftp_connection(
            self._sftp_credentials_hd['hostname_get_nominative_from_ODS'],
            self._sftp_credentials_hd['port_get_nominative_from_ODS'],
            self._sftp_credentials_hd['username_get_nominative_from_ODS'],
            self._sftp_credentials_hd['password_get_nominative_from_ODS'])

    def _open_sftp_connection_send_genomic_to_ods(self) -> (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Public function to open an SFTP connection to the location where genomic files need to be deposited by bioit.
        :return: an ssh and sftp client for further use
        """
        return self.__open_sftp_connection(
            self._sftp_credentials_hd['hostname_send_genomic_to_ODS'],
            self._sftp_credentials_hd['port_send_genomic_to_ODS'],
            self._sftp_credentials_hd['username_send_genomic_to_ODS'],
            self._sftp_credentials_hd['password_send_genomic_to_ODS'])

    def __enter__(self):
        """
        Enter the runtime context related to the class (interest: connections).
        __enter__/__exit__ methods are used to get the context manager to call the class in a "with" statement
        """
        return self

    def __exit__(self, *args, **kwargs) -> None:
        """
        Closes the db connections at the end of the run.
        __enter__/__exit__ are used to get the context manager to call the class in a "with" statement.
        """
        self.close_sftp_connection()
