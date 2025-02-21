# Script should be run ever 12h in order to limit the nr of mails

import json
import logging
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
from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD, CODES_GENOMIC_ODS
from bioit_nrc_integration.python.util.sftp_connection import SFTPConnection

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


class ErrorCheckerForMainSenderToHD(SFTPConnection):
    """
    During discussions with both ODS and DWH it was decided that input files that failed would be moved to the error
    folder together with a log file with the same name but log appendix. This function checks if new errors were raised
    and prompts manual investigation through email preferably every 12h.
    """
    def __init__(self, test_dummy: bool = False, alternate_dtap: str = None) -> None:
        """
        Initializes this class and executes the main function.
        :param test_dummy: Whether the test dummy should be processed or if the main function should run normally
        :param alternate_dtap: alternative dtap (should take test or prod from mongo config) in case we want to test
        dev or acc.
        :return: None
        """
        super().__init__()

        self._test_dummy = test_dummy
        self._alternate_dtap = alternate_dtap

        self._mongo_config_data = get_mongodb_config_data()
        # get sftp credentials
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)
        # get HD ODS dictionaries to be able to translate to usable text
        with CODES_GENOMIC_ODS.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)

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
        ssh, sftp, folder_path = self.__open_sftp_and_set_folder_path('error')

        # List all files in the remote directory
        files_and_dirs = sftp.listdir_attr(folder_path)

        # close SFTP after having received necessary info
        self._close_sftp_connection(ssh, sftp)

        # Filter out directories, only list files
        error_files_count = len([entry.filename for entry in files_and_dirs if not stat.S_ISDIR(entry.st_mode)])
        # need to divide files by 2 because we have decided to also add .log files.
        # it remains to be seen if they actually do but it needs to be implemented here nevertheless
        error_count = error_files_count / 2
        if error_count > 0:
            send_email(f"Found {error_count} "
                       f"errors in the ODS SFTP error folder. Please go "
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
        ssh, sftp, folder_path = self.__open_sftp_and_set_folder_path('processed')

        # List all files in the remote directory
        files_and_dirs = sftp.listdir_attr(folder_path)

        # Filter out directories, only list files
        files_remote = [entry.filename for entry in files_and_dirs if not stat.S_ISDIR(entry.st_mode)]
        if self._test_dummy:
            files_remote = [file for file in files_remote if file.startswith('test_dummy')]
        logging.info(files_remote)

        with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
            # Download each file
            for file in files_remote:
                sftp.get(f'{folder_path}/{file}', f'{temp_json_dir}/{file}')
                logging.info(f'Downloaded: {file}')

                with Path(f'{temp_json_dir}/{file}').open('r') as handle:
                    contents = json.load(handle)
                dcd_name = contents['metadata']['dcd_name']
                # get species name based on dcd name which is a metadata value in both outgoing DCDs
                species = next(pathogen for pathogen, details in self._translation_codes['pathogens'].items() if details['dcd_name'] == dcd_name)
                # Open correct pathogen specific MongoDB database
                mongoinit_azure = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                                      selected_connection_string='CONNECTION_STRING_AZURE',
                                                      alternate_dtap=self._alternate_dtap)
                isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
                    isolates_resequencing_collection = mongoinit_azure.initialise_collections()
                isolates_collection.update_one({'_id': contents['data']['TX_BIOIT_TECHNICAL_ID']},
                                               {"$set": {f"accepted_by_ODS": True,
                                                         f"changes_accepted_by_ODS": True}})
                # the 'changes_accepted_by_ODS' field interplays with 'changed_since_sent_to_ODS' that is set by
                # MainMongo and modified by main_sender_to_HD;
                # every time a reanalysis detects a change in the sendable fields, both the changed and accepted
                # fields are set to True and False respectively.
                # At this point in the script they would be False and True respectively again which is the end-state.

                # Remove sftp file in processed folder once acknowledged and inserted into MongoDB local
                sftp.remove(f'{folder_path}/{file}')

            # close SFTP after having executed the function
            self._close_sftp_connection(ssh, sftp)

    def __open_sftp_and_set_folder_path(self, folder: str) -> (paramiko.SSHClient, paramiko.SFTPClient, str):
        """
        opens sftp and sets folder path for a given healthdata receiver
        :param folder: desired folder in sftp location, error or processed
        :return: ssh, sftp, folder_path as str
        """
        ssh, sftp = self._open_sftp_connection(
            self._sftp_credentials_hd['hostname_send_genomic_to_ODS'],
            self._sftp_credentials_hd['port_send_genomic_to_ODS'],
            self._sftp_credentials_hd['username_send_genomic_to_ODS'],
            self._sftp_credentials_hd['password_send_genomic_to_ODS'])
        folder_path = 'upload/' + \
                      f"{(self._alternate_dtap + '/') if self._alternate_dtap else ''}" + \
                      folder
        return ssh, sftp, folder_path


if __name__ == '__main__':
    ErrorCheckerForMainSenderToHD()
