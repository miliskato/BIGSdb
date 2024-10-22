from typing import Union

import paramiko


class SFTPConnection:
    """
    Base Class containing functions to handle an SFTP connection.
    """
    def __init__(self) -> None:
        """
        Initializes this class.
        :return: None
        """
        pass

    @staticmethod
    def _open_sftp_connection(hostname: str, port: Union[str, int], username: str, password: str) -> (paramiko.SSHClient, paramiko.SFTPClient):
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
    def _close_sftp_connection(ssh: paramiko.SSHClient, sftp: paramiko.SFTPClient) -> None:
        """
        Closes the SSH and SFTP clients created by open_sftp_connection.
        :return: None
        """
        sftp.close()
        ssh.close()
