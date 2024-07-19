import json
import logging
import socket
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

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# SFTP connection parameters
hostname = 'hera-dc.healthdata.be'
port = 2222  # Default SFTP port
username = 'to_be_replaced_by_ansible'
password = 'to_be_replaced_by_ansible'

# Create an SSH client
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())


# def move_file_sftp(sftp, filename, success: bool) -> None:

class MainNominativeDataParserFromOds:
    """
    Class that downloads all nominative metadata JSONs from the ODS SFTP, parses them, inserts the contents in MongoDB if valid,
    and finally moves them to the correct sftp location based on whether the parsing was successful, either 'processed' or 'error'.
    """

    def __init__(self) -> None:
        """
        Intialises this class and executes the main function.
        :return: None
        """
        # initialize lists of successful and failed filenames:
        self._files_remote = []
        self._files_processed = []
        self._files_error = []

        # initialize dictionary to match CLIN and LAB files by business key
        self._files_by_business_key_by_species = {}

        # initialize ssh & sftp
        self._ssh, self._sftp = self._open_sftp_connection()

        # get mongodb config data
        self._mongo_config_data = get_mongodb_config_data()

        # get HD ODS dictionaries to be able to translate to useable text
        with (Path(__file__).resolve().parent / 'config' / 'codes_get_nominative_from_ODS.yml').open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)

        try:
            with tempfile.TemporaryDirectory(dir='/tmp') as self._temp_json_dir:
                self._download_json_files()
                # close after downloading the json files to not risk reaching the inactivity time limit
                self._close_sftp_connection()

                self._match_files_according_to_business_key_and_group_by_pathogen()
                self._process_json_files()

            # reinitialize ssh & sftp
            self._ssh, self._sftp = self._open_sftp_connection()

            # In SFTP moving is done by renaming; move files to right folder according to success
            # for file in self._files_processed:
            #     self._sftp.rename(f'upload/test/{file}', f'upload/processed/{file}')
            # for file in self._files_error:
            #     self._sftp.rename(f'upload/test/{file}', f'upload/error/{file}')
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: {exceptionmessage}\n{traceback.format_exc()}")

    def _open_sftp_connection(self) -> (paramiko.SSHClient, paramiko.SFTPClient):
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

    def _download_json_files(self):
        """
        Downloads all new files because in sftp files can not be read, so they need to be downloaded.
        :return: None
        """
        # List all files in the remote directory
        self._files_remote = self._sftp.listdir('upload')
        logging.info(self._files_remote)

        # Download each file
        for file in self._files_remote:
            self._sftp.get(f'upload/{file}', f'{self._temp_json_dir}/{file}')
            logging.info(f'Downloaded: {file}')

    def _match_files_according_to_business_key_and_group_by_pathogen(self):
        """
        The filenames uploaded by the HD ODS do not have any significance except for the CLIN or LAB part.
        Files therefore need to be matched based on their tx_business_key 's.
        This function parses all downloaded JSON files and tries to match the business keys and groups them by pathogen.
        :return: None
        """
        files_by_business_key = {}
        for file in self._files_remote:
            filetype = 'CLIN' if '_CLIN_' in file else 'LAB' if '_LAB_' in file else None
            if not filetype:
                # ignore files that do not contain either CLIN or LAB in their filename
                continue
            with Path(f'{self._temp_json_dir}/{file}').open('r') as handle:
                contents = json.load(handle)
                business_key = contents['data']['tx_business_key']
                species = self._translation_codes['pathogens'][contents['metadata']['data_collection']]
            if not files_by_business_key.get(species):
                # initialise pathogen key
                files_by_business_key[species] = {}
            if not files_by_business_key[species].get(contents['data']['tx_business_key']):
                # add first file
                files_by_business_key[species][business_key] = {filetype: file}
            else:
                # add second file
                files_by_business_key[species][business_key][filetype] = file
        # only retain the matched files (length of business_key dict is 2 because there is 
        # one value for CLIN and one for LAB)
        self._files_by_business_key_by_species = {k: {sub_k: sub_v for sub_k, sub_v in v.items() if len(sub_v) == 2} 
                                                  for k, v in files_by_business_key.items()}

    def _process_json_files(self):
        """
        Parses all downloaded JSON files and inserts them into MongoDB
        :return: None
        """
        for species, business_key_dicts in self._files_by_business_key_by_species:
            mongoinit_local = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                                  alternate_connection_string=self._mongo_config_data[
                                                      'CONNECTION_STRING_LOCAL'])
            nominative_labtest_clinical_metadata_collection = mongoinit_local.initialise_nominative_labtest_clinical_metadata_collection()
            unprocessed_nominative_labtest_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_labtest_metadata_collection()
            unprocessed_nominative_clinical_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_clinical_metadata_collection()
            for business_key, pair in business_key_dicts:
                # initialise translation dict
                data_translated = {'_id': business_key}
                # initialise unprocessed data dict
                data_unprocessed = {'CLIN': {}, 'LAB': {}}
                for filetype in ['CLIN', 'LAB']:
                    try:
                        with Path(f'{self._temp_json_dir}/{pair[filetype]}').open('r') as handle:
                            contents = json.load(handle)
                        data = contents['data']

                        # loop over schema
                        for hd_key, hd_key_property_dict in self._translation_codes['schema'][filetype]:
                            # Get value capitalisation agnostically
                            unprocessed_value = data.get(hd_key.lower()) if data.get(hd_key.lower()) else data.get(hd_key)
                            if data.get(unprocessed_value):
                                if hd_key_property_dict.get('code_list'):
                                    value = self._translation_codes['code_lists'][hd_key_property_dict['code_list']][unprocessed_value]
                                else:
                                    value = unprocessed_value
                                data_translated[hd_key_property_dict['translation']] = value
                            else:
                                if hd_key_property_dict['required'] is False:
                                    data_translated[hd_key_property_dict['translation']] = hd_key_property_dict['default']
                                else:
                                    raise f"key {hd_key} is missing but is required in {filetype} file!!"
                        data_unprocessed[filetype] = data
                        # add id to be able to find in MongoDB
                        data_unprocessed[filetype]['_id'] = business_key
                    except:
                        # todo discuss if error message needs to be appended?
                        self._files_error.append(pair[filetype])
                    # Insert all documents into MongoDB after having succesfully parsed the matching files
                    nominative_labtest_clinical_metadata_collection.insert_one(data_translated)
                    unprocessed_nominative_labtest_metadata_collection.insert_one(data_unprocessed['LAB'])
                    unprocessed_nominative_clinical_metadata_collection.insert_one(data_unprocessed['CLIN'])
                    self._files_processed.extend([pair["LAB"], pair["CLIN"]])

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


if __name__ == '__main__':
    # run main
    MainNominativeDataParserFromOds()
