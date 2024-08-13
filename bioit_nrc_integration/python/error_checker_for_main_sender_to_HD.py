# Script should be run ever 12h in order to limit the nr of mails

import json
import logging
import math
import stat
import sys
import tempfile
import traceback
import yaml
from pathlib import Path

import paramiko

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email
from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD, CODES_GENOMIC_DWH

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

mongo_config_data = get_mongodb_config_data()

fail_log_dict = {}


class ErrorCheckerForMainSenderToHD:
    """
    During discussions with both ODS and DWH it was decided that input files that failed would be moved to the error
    folder together with a log file with the same name but log appendix. This function checks if new errors were raised
    and prompts manual investigation through email preferably every 12h
    """
    def __init__(self) -> None:
        """
        Initializes this class and executes the main function.
        """
        self._mongo_config_data = mongo_config_data
        # get sftp credentials
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)
        # get HD ODS dictionaries to be able to translate to useable text
        with CODES_GENOMIC_DWH.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)

        self._fail_log_dict = {'ODS': 0, 'DWH': 0}

        try:
            self._main_error_checker_for_main_sender_to_hd()
            self._main_processed_files_acknowledger()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise

    def _main_error_checker_for_main_sender_to_hd(self) -> None:
        """
        Main function to check for errors.
        This function aggregates the errors to not spam the mailbox. If there are none, it doesn't do anything.
        Should not raise errors by itself, but if it does, they are caught in the main try except.
        :return: None
        """
        for healthdata_receiver in ['ODS', 'DWH']:
            ssh, sftp = self.__open_sftp_connection(healthdata_receiver)
            folder_path = 'error'
            if healthdata_receiver == 'DWH':
                folder_path = 'from_hd/' + \
                              f"{self._mongo_config_data['dtap'] + '/' if self._mongo_config_data['dtap'] != 'prod' else ''}" + \
                              folder_path
            # List all files in the remote directory
            files_and_dirs = sftp.listdir_attr(folder_path)

            # close SFTP after having received necessary info
            sftp.close()
            ssh.close()

            # Filter out directories, only list files
            error_files_count = sum(entry.filename for entry in files_and_dirs if not stat.S_ISDIR(entry.st_mode))
            # need to divide files by 2 because we have decided to also add .log files.
            # it remains to be seen if they actually do but it needs to be implemented here nevertheless
            self._fail_log_dict[healthdata_receiver] = error_files_count / 2
        if sum(error_count for healtdata_receiver, error_count in self._fail_log_dict.items()) > 0:
            send_email(f"Found {self._fail_log_dict['ODS']} and {self._fail_log_dict['DWH']} "
                       f"errors in the ODS and DWH SFTP error folders respectively. Please go "
                       f"and investigate manually, resolve the errors using the .log files, add the correct file to "
                       f"the root location again and remove the error and log files.")

    def _main_processed_files_acknowledger(self) -> None:
        """
        Main function to acknowledge processed files, insert this acknowledgement in the local MongoDB, and remove
        the files from the processed folder.
        This function should not fail because all inputs were defined by us in the main_sender_to_HD, and if it does
        there is something seriously wrong (like no access to sftp) and it will be caught in the main try except.
        :return: None
        """
        for healthdata_receiver in ['ODS', 'DWH']:
            ssh, sftp = self.__open_sftp_connection(healthdata_receiver)
            folder_path = 'processed'
            if healthdata_receiver == 'DWH':
                folder_path = 'from_hd/' + \
                              f"{self._mongo_config_data['dtap'] + '/' if self._mongo_config_data['dtap'] != 'prod' else ''}" + \
                              folder_path

            # List all files in the remote directory
            files_and_dirs = sftp.listdir_attr(folder_path)

            # Filter out directories, only list files
            files_remote = [entry.filename for entry in files_and_dirs if not stat.S_ISDIR(entry.st_mode)]
            logging.info(files_remote)

            with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
                # Download each file
                for file in files_remote:
                    sftp.get(f'{folder_path}/{file}', f'{temp_json_dir}/{file}')
                    logging.info(f'Downloaded: {file}')

                    with Path(f'{temp_json_dir}/{file}') as handle:
                        contents = json.loads(handle)
                    dcd_name = contents['metadata']['dcd_name']
                    # get species name based on dcd name which is a metadata value in both outgoing DCDs
                    species = next(pathogen for pathogen, details in self._translation_codes['pathogens'].items() if details['dcd_name'] == dcd_name)
                    # Open correct pathogen specific MongoDB database
                    mongoinit_local = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                                          alternate_connection_string=self._mongo_config_data['CONNECTION_STRING_LOCAL'])
                    mapping_table_collection = mongoinit_local.initialise_mapping_table_collection()
                    mapping_table_collection.update_one({'TX_BUSINESS_KEY': contents['data']['TX_BUSINESS_KEY']},
                                                        {"$set": {f"accepted_by_{healthdata_receiver}": True}})
                    # Remove sftp file in processed folder once acknowledged and inserted into MongoDB local
                    sftp.remove(f'{folder_path}/{file}')

            # close SFTP after having executed the function
            sftp.close()
            ssh.close()

    def __open_sftp_connection(self, healthdata_receiver: str) -> (paramiko.SSHClient, paramiko.SFTPClient):
        """
        Opens an SSH and SFTP connection using variables defined in the sftp credentials configuration file.
        :param healthdata_receiver: either DWH or ODS
        :return: an ssh and sftp client for further use
        """
        # Create an SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the server
        if healthdata_receiver == 'ODS':
            ssh.connect(self._sftp_credentials_hd['hostname_send_mapping_table_to_ODS'],
                        self._sftp_credentials_hd['port_send_mapping_table_to_ODS'],
                        self._sftp_credentials_hd['username_send_mapping_table_to_ODS'],
                        self._sftp_credentials_hd['password_send_mapping_table_to_ODS'])
        else:  # if healthdata_receiver == 'DWH':
            ssh.connect(self._sftp_credentials_hd['hostname_send_genomic_to_DWH'],
                        self._sftp_credentials_hd['port_send_genomic_to_DWH'],
                        self._sftp_credentials_hd['username_send_genomic_to_DWH'],
                        self._sftp_credentials_hd['password_send_genomic_to_DWH'])

        # Create an SFTP session
        sftp = ssh.open_sftp()
        return ssh, sftp


if __name__ == '__main__':
    ErrorCheckerForMainSenderToHD()
