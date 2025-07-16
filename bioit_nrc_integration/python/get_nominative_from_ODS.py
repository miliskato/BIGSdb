import json
import logging
import stat
import sys
import tempfile
import traceback
from pathlib import Path

import yaml
from pymongo.errors import DuplicateKeyError

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import send_email
from bioit_nrc_integration.python.config import CODES_NOMINATIVE_ODS
from bioit_nrc_integration.python.util.get_clin_lab_json_parser import get_clin_lab_json_parser
from bioit_nrc_integration.python.util.sftp_connection_ods import SFTPConnectionODS

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


class GetNominativeFromOds:
    """
    Class that downloads all nominative metadata JSONs from the ODS SFTP, parses them,
    inserts the contents in MongoDB if valid,
    and finally moves them to the correct sftp location based on whether the parsing was successful,
    either 'processed' or 'error'.
    """
    def __init__(self, test_dummy: bool = False, alternate_dtap: str = None) -> None:
        """
        Initialises this class and executes the main function.
        :param test_dummy: Whether the test dummy should be processed or if the main function should run normally
        :param alternate_dtap: alternative dtap (should take test or prod from mongo config) in case
        we want to test dev or acc
        :return: None
        """
        self._test_dummy = test_dummy
        self._alternate_dtap = alternate_dtap
        
        # initialize lists of successful and failed filenames:
        self._files_remote = []
        self._files_processed = []
        self._files_error = []
        self._files_error_logs = {}
        
        # set base sftp dir
        self._base_sftp_dir = f"upload/{(self._alternate_dtap + '/') if self._alternate_dtap else ''}"

        # initialize dictionary to match CLIN and LAB files by pathogen
        self._files_by_filetype_by_species = {}

        # get mongodb config data
        self._mongo_config_provider = MongoConfigProvider(alternate_dtap)

        # get HD ODS dictionaries to be able to translate to usable text
        with CODES_NOMINATIVE_ODS.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)

        try:
            # initialize ssh & sftp
            with tempfile.TemporaryDirectory(dir='/tmp') as self._temp_json_dir:
                with SFTPConnectionODS('get') as self._sftp_connection_ods:
                    self._download_json_files()
                    # close after downloading the json files to not risk reaching the inactivity time limit

                # Execute local code that doesn't need SFTP connection
                self._group_files_by_pathogen_and_type()
                self._process_json_files()

                with SFTPConnectionODS('get') as self._sftp_connection_ods:
                    # In SFTP moving is done by renaming; move files to right folder according to success
                    self._move_files_according_to_success()

        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise

    def _download_json_files(self) -> None:
        """
        Downloads all new files because in sftp files can not be read, so they need to be downloaded.
        :return: None
        """
        # List all files in the remote directory non-recursively
        files_and_dirs = self._sftp_connection_ods.sftp.listdir_attr(self._base_sftp_dir)

        # Filter out directories, only list files
        self._files_remote = [entry.filename for entry in files_and_dirs if not stat.S_ISDIR(entry.st_mode)]
        if self._test_dummy:
            self._files_remote = [file for file in self._files_remote if file.startswith('test_dummy')]
        logging.info(self._files_remote)

        # Download each file
        for file in self._files_remote:
            self._sftp_connection_ods.sftp.get(f'{self._base_sftp_dir}{file}', f'{self._temp_json_dir}/{file}')
            logging.info(f'Downloaded: {file}')

    def _group_files_by_pathogen_and_type(self) -> None:
        """
        The filenames uploaded by the HD ODS do not have any significance except for the CLIN or LAB part.
        Files therefore need to be grouped by this CLIN or LAB because they are parsed differently ( because they
        contain different fields) and by pathogen which is found in the file itself.
        This function parses all downloaded JSON files and groups them by filetype (filename) and
        by pathogen (file contents).
        :return: None
        """
        for file in self._files_remote:
            filetype = 'CLIN' if '_CLIN_' in file else 'LAB' if '_LAB_' in file else None
            if not filetype:
                # ignore files that do not contain either CLIN or LAB in their filename
                continue
            try:
                with Path(f'{self._temp_json_dir}/{file}').open('r') as handle:
                    contents = json.load(handle)
                    species = self._translation_codes['pathogens'].get(contents['metadata']['dataCollection'])
                    if not species:
                        continue
            except Exception as exceptionmessage:
                logging.info(f"{exceptionmessage}\n{traceback.format_exc()}")
                self._files_error.append(file)
                self._files_error_logs[file] = f"{exceptionmessage}\n{traceback.format_exc()}"
                continue  # move on to next file
            if not self._files_by_filetype_by_species.get(species):
                # initialise pathogen key
                self._files_by_filetype_by_species[species] = {'CLIN': [], 'LAB': []}
            self._files_by_filetype_by_species[species][filetype].append(file)

    def _process_json_files(self) -> None:
        """
        Parses all downloaded JSON files and inserts them into MongoDB.
        The processed CLIN and LAB files are combined into a single MongoDB document in the
        nominative_labtest_clinical_metadata collection with the _id == the tx_business_key which is common between
        both BUT different from the tx_business_key received in the WGSMeta received in Azure.
        :return: None
        """
        for species, filetypes_dict in self._files_by_filetype_by_species.items():
            mongoinit_local = MongoInitialisation(species, self._mongo_config_provider.get_local_connection_string(species), self._mongo_config_provider.dtap)
            nominative_labtest_clinical_metadata_collection = mongoinit_local.initialise_nominative_labtest_clinical_metadata_collection()
            unprocessed_nominative_labtest_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_labtest_metadata_collection()
            unprocessed_nominative_clinical_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_clinical_metadata_collection()

            selected_parser = get_clin_lab_json_parser(species)
            for filetype, files in filetypes_dict.items():
                for file in files:
                    try:
                        with Path(f'{self._temp_json_dir}/{file}').open('r') as handle:
                            contents = json.load(handle)
                        data_unprocessed = contents['data']

                        # Parse data_unprocessed
                        parser_instance = selected_parser(data_unprocessed, filetype, species, self._translation_codes)
                        data_translated = parser_instance.run()

                    except Exception as exceptionmessage:
                        logging.info(f"{exceptionmessage}\n{traceback.format_exc()}")
                        self._files_error.append(file)
                        self._files_error_logs[file] = f"{exceptionmessage}\n{traceback.format_exc()}"
                        continue  # do not insert in MongoDB and move on to next file
                    # Insert document into MongoDB after having successfully parsed the matching files
                    # use upsert to create the document if it doesn't exist and update if it does
                    nominative_labtest_clinical_metadata_collection.update_one({'_id': data_translated['_id']},
                                                                               {'$set': {**data_translated, f"{filetype}_received": True}},
                                                                               upsert=True)

                    # if one of these raises a pymongo DuplicateKeyError possibly because the documents have been
                    # inserted into MongoDB previously but failed before moving them to the
                    # processed sftp location, then the entire flow is stopped.
                    # If the error were to be caught and an email sent per failure, then a lot of emails might be sent.
                    # Therefore, as a solution, duplicate key errors are skipped. If another error occurs
                    # (can not currently imagine one), then (a lot of) emails might be sent after all
                    try:
                        if filetype == 'LAB':
                            unprocessed_nominative_labtest_metadata_collection.insert_one(data_unprocessed)
                        if filetype == 'CLIN':
                            unprocessed_nominative_clinical_metadata_collection.insert_one(data_unprocessed)
                    except DuplicateKeyError:
                        pass
                    self._files_processed.append(file)

    def _move_files_according_to_success(self) -> None:
        """
        After having executed the entire rest of this script, move the files to the processed or error folder
        depending on the success of their parsing. If moved to the error folder, also add a log file.
        :return: None
        """
        for file in self._files_processed:
            self._sftp_connection_ods.sftp.rename(f'{self._base_sftp_dir}{file}', f'{self._base_sftp_dir}processed/{file}')
        for file in self._files_error:
            self._sftp_connection_ods.sftp.rename(f'{self._base_sftp_dir}{file}', f'{self._base_sftp_dir}error/{file}')
        for filename, contents in self._files_error_logs.items():
            error_log_filename = '.'.join(filename.split('.')[:-1]) + '.log'
            error_log_file = Path(self._temp_json_dir) / error_log_filename
            with error_log_file.open('w') as handle:
                handle.write(contents)
            self._sftp_connection_ods.sftp.put(str(error_log_file), f'{self._base_sftp_dir}error/{error_log_filename}')


if __name__ == '__main__':
    # run main
    GetNominativeFromOds()
