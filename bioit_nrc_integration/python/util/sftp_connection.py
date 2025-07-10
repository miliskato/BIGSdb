from typing import Union

import paramiko
import yaml

from ..config import SFTP_CREDENTIALS_HD


class SFTPConnection:
    """
    Base Class containing functions to handle an SFTP connection.
    """
    def __init__(self) -> None:
        """
        Initializes this class.
        :return: None
        """
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)

    @staticmethod
    def _open_sftp_connection(hostname: str, port: Union[str, int], username: str, password: str) -> \
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

    @staticmethod
    def close_sftp_connection(ssh: paramiko.SSHClient, sftp: paramiko.SFTPClient) -> None:
        """
        Closes the SSH and SFTP clients created by open_sftp_connection.
        :return: None
        """
        sftp.close()
        ssh.close()

    def open_sftp_connection_get_nominative_from_ods(self) -> (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Public function to open an SFTP connection to the location where nominative files are deposited by the ODS.
        :return: an ssh and sftp client for further use
        """
        return self._open_sftp_connection(
            self._sftp_credentials_hd['hostname_get_nominative_from_ODS'],
            self._sftp_credentials_hd['port_get_nominative_from_ODS'],
            self._sftp_credentials_hd['username_get_nominative_from_ODS'],
            self._sftp_credentials_hd['password_get_nominative_from_ODS'])

    def open_sftp_connection_send_genomic_to_ods(self) -> (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Public function to open an SFTP connection to the location where genomic files need to be deposited by bioit.
        :return: an ssh and sftp client for further use
        """
        return self._open_sftp_connection(
            self._sftp_credentials_hd['hostname_send_genomic_to_ODS'],
            self._sftp_credentials_hd['port_send_genomic_to_ODS'],
            self._sftp_credentials_hd['username_send_genomic_to_ODS'],
            self._sftp_credentials_hd['password_send_genomic_to_ODS'])
