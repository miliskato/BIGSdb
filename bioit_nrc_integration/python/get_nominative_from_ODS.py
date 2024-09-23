import json
import logging
import math
import stat
import sys
import tempfile
import traceback
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pymongo.errors import DuplicateKeyError

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email
from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD, CODES_NOMINATIVE_ODS
from bioit_nrc_integration.python.util.sftp_connection import SFTPConnection

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


class MainNominativeDataParserFromOds(SFTPConnection):
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
        super().__init__()

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
        self._mongo_config_data = get_mongodb_config_data()

        # get HD ODS dictionaries to be able to translate to useable text
        with CODES_NOMINATIVE_ODS.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)
        # get sftp credentials
        with SFTP_CREDENTIALS_HD.open('r') as handle:
            self._sftp_credentials_hd = yaml.safe_load(handle)

        try:
            # initialize ssh & sftp
            self._ssh, self._sftp = self._open_sftp_connection(
                self._sftp_credentials_hd['hostname_get_nominative_from_ODS'],
                self._sftp_credentials_hd['port_get_nominative_from_ODS'],
                self._sftp_credentials_hd['username_get_nominative_from_ODS'],
                self._sftp_credentials_hd['password_get_nominative_from_ODS'])

            with tempfile.TemporaryDirectory(dir='/tmp') as self._temp_json_dir:
                self._download_json_files()
                # close after downloading the json files to not risk reaching the inactivity time limit
                self._close_sftp_connection(self._ssh, self._sftp)

                self._group_files_by_pathogen_and_type()
                self._process_json_files()

                # reinitialize ssh & sftp
                self._ssh, self._sftp = self._open_sftp_connection(
                    self._sftp_credentials_hd['hostname_get_nominative_from_ODS'],
                    self._sftp_credentials_hd['port_get_nominative_from_ODS'],
                    self._sftp_credentials_hd['username_get_nominative_from_ODS'],
                    self._sftp_credentials_hd['password_get_nominative_from_ODS'])

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
        files_and_dirs = self._sftp.listdir_attr(self._base_sftp_dir)

        # Filter out directories, only list files
        self._files_remote = [entry.filename for entry in files_and_dirs if not stat.S_ISDIR(entry.st_mode)]
        if self._test_dummy:
            self._files_remote = [file for file in self._files_remote if file.startswith('test_dummy')]
        logging.info(self._files_remote)

        # Download each file
        for file in self._files_remote:
            self._sftp.get(f'{self._base_sftp_dir}{file}', f'{self._temp_json_dir}/{file}')
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
                    species = self._translation_codes['pathogens'][contents['metadata']['data_collection']]
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
        :return: None
        """
        for species, filetypes_dict in self._files_by_filetype_by_species.items():
            mongoinit_local = MongoInitialisation(species, mongo_config_data=self._mongo_config_data,
                                                  alternate_connection_string=self._mongo_config_data[
                                                      'CONNECTION_STRING_LOCAL'],
                                                  alternate_dtap=self._alternate_dtap)
            nominative_labtest_clinical_metadata_collection = mongoinit_local.initialise_nominative_labtest_clinical_metadata_collection()
            unprocessed_nominative_labtest_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_labtest_metadata_collection()
            unprocessed_nominative_clinical_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_clinical_metadata_collection()
            for filetype, files in filetypes_dict.items():
                for file in files:
                    # initialise translation dict
                    data_translated = {}
                    try:
                        with Path(f'{self._temp_json_dir}/{file}').open('r') as handle:
                            contents = json.load(handle)
                        data_unprocessed = contents['data']

                        self.__parse_input_json(data_unprocessed, data_translated, filetype, species)

                    except Exception as exceptionmessage:
                        logging.info(f"{exceptionmessage}\n{traceback.format_exc()}")
                        self._files_error.append(file)
                        self._files_error_logs[file] = f"{exceptionmessage}\n{traceback.format_exc()}"
                        continue  # do not insert in MongoDB and move on to next file
                    # Insert document into MongoDB after having successfully parsed the matching files
                    # use upsert to create the document if it doesn't exist and update if it does
                    nominative_labtest_clinical_metadata_collection.update_one({'_id': data_translated['_id']},
                                                                               {'$set': {**data_translated}},
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

    def __parse_input_json(self, data_unprocessed: Dict[str, Any], data_translated: Dict[str, Any], filetype: str, species: str) -> None:
        """
        Parses the input JSON file and translates the fields & values to usable values for the NRC platform.
        :param data_unprocessed: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :param filetype: CLIN or LAB
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: None
        """
        if filetype == 'LAB':
            self.___calculate_age_fields(data_unprocessed, data_translated)
            self.___parse_complex_labtest_results(data_unprocessed, data_translated)
        if filetype == 'CLIN':
            self.___parse_complex_country_field(data_unprocessed, data_translated)
            if species == 'salmonella':
                self.___parse_salmonella_symptom_fields(data_unprocessed, data_translated)
        # loop over schema
        for hd_key, hd_key_property_dict in self._translation_codes['schema'][filetype].items():
            unprocessed_value = self.___get_value_by_capitalization_agnostic_key(data_unprocessed, hd_key)
            if unprocessed_value:
                if hd_key_property_dict.get('code_list'):
                    value = self._translation_codes['code_lists'][hd_key_property_dict['code_list']][
                        self.___cast_as_int_if_int(unprocessed_value)]
                else:
                    value = unprocessed_value
                data_translated[hd_key_property_dict['translation']] = value
            else:
                if hd_key_property_dict['required'] is False:
                    if hd_key_property_dict.get('default'):
                        data_translated[hd_key_property_dict['translation']] = hd_key_property_dict['default']
                else:
                    raise f"key {hd_key} is missing but is required in {filetype} file!!"
        # add id to be able to find in MongoDB
        data_unprocessed['_id'] = data_translated['_id']  # data_translated['_id'] == data_unprocessed['TX_BUSINESS_KEY']

    @staticmethod
    def ___calculate_age_fields(data_unprocessed: Dict[str, Any], data_translated: Dict[str, Any]) -> None:
        """
        Calculates the two age fields patient_age and patient_age_group from the DOB and the collection date.
        :param data_unprocessed: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :return: None
        """
        # DOB is not a mandatory field so it can be missing = None
        dob = MainNominativeDataParserFromOds.___get_value_by_capitalization_agnostic_key(data_unprocessed, 'DT_PAT_DOB')
        if dob:
            # Calculate the number of years
            # Average year length considering leap years = 365.25 days
            patient_age = math.floor((datetime.strptime(MainNominativeDataParserFromOds.___get_value_by_capitalization_agnostic_key(data_unprocessed, 'DT_LAB_COLLCN'), "%Y-%m-%dT%H:%M:%S") -
                                      datetime.strptime(dob, "%Y-%m-%d")).days / 365.25)
            data_translated['patient_age'] = patient_age
            age_groups = [
                ("Below 1", -1, 0),
                ("Between 1 and 4", 1, 4),
                ("Between 5 and 9", 5, 9),
                ("Between 10 and 14", 10, 14),
                ("Between 15 and 19", 15, 19),
                ("Between 20 and 24", 20, 24),
                ("Between 25 and 44", 25, 44),
                ("Between 45 and 64", 45, 64),
                ("65 and above", 65, 150)
            ]
            data_translated['patient_age_group'] = next(
                (group for group, start, end in age_groups if start <= patient_age <= end))
        else:
            # in Salmonella test unknowns for patient_age and patient_age_group are encoded as UNK
            data_translated['patient_age'] = 'UNK'
            data_translated['patient_age_group'] = 'UNK'

    def ___parse_complex_labtest_results(self, data_unprocessed: Dict[str, Any], data_translated: Dict[str, Any]) -> None:
        """
        Parses the labtest results from a complex list of dictionaries # todo
        e.g. "tx_ttl_lab_test": [{"dt_lab_test": "2024-03-25T12:00:00",  "tx_lab_rr_ll": "ref low",  "tx_lab_rr_ul": "ref up",  "cd_lab_pnl_batt": "385432009",  "cd_lab_rslt_sta": "corrected",  "cd_lab_reslt_tpe": "19851009",  "cd_lab_rslt_flag": "260405006",  "cd_lab_test_code": "468-9",  "cd_lab_test_meth": "14788002",  "ms_lab_rr_ll_val": 11.00000,  "ms_lab_rr_ul_val": 150.00000,  "cd_lab_rr_ll_unit": "385432009",  "cd_lab_rr_ul_unit": "385432009",  "cd_lab_intrpr_meth": "261665006",  "tx_lab_rslt_intrpr": "Test 3 interpretation",  "tx_lab_test_rslt_id": "Test Result 3",  "cd_lab_test_rslt_sta": "preliminary",  "tx_lab_cmnt_test_rslt": "Lab Test 3 comment",  "ms_lab_test_rslt_qn_val": 99.00000,  "cd_lab_test_rslt_qn_unit": "385432009"}, {"dt_lab_test": "2024-02-06T12:00:00",  "tx_lab_rr_ll": "lower limit",  "tx_lab_rr_ul": "Ref upper Range",  "cd_lab_pnl_batt": "385432009",  "cd_lab_rslt_sta": "registered",  "cd_lab_reslt_tpe": "252275004",  "cd_lab_rslt_flag": "281300000",  "cd_lab_test_code": "TC0031",  "cd_lab_test_meth": "363779003",  "ms_lab_rr_ll_val": 55.00000,  "ms_lab_rr_ul_val": 66.00000,  "cd_lab_rr_ll_unit": "385432009",  "cd_lab_rr_ul_unit": "385432009",  "cd_lab_intrpr_meth": "IM0001",  "tx_lab_rslt_intrpr": "Res Interpretation",  "cd_lab_test_rslt_ql": "83185005",  "tx_lab_test_rslt_id": "TestResID",  "cd_lab_test_rslt_sta": "preliminary",  "tx_lab_cmnt_test_rslt": "Lab Test comment"}]
        :param data_unprocessed: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :return: None
        """
        labtest_list_of_result_dicts = self.___get_value_by_capitalization_agnostic_key(data_unprocessed, 'TX_TTL_LAB_TEST')
        if labtest_list_of_result_dicts:
            for labtest_result_dict in labtest_list_of_result_dicts:
                labtest_result_combinations = self._translation_codes['code_lists']['TX_TTL_LAB_TEST_combinations']
                labtest_dict = next((labtest_dict for labtest_dict in labtest_result_combinations if
                                     # CD_LAB_TEST_METH is mandatory I believe
                                     labtest_dict['CD_LAB_TEST_METH'] == self.___get_value_by_capitalization_agnostic_key(labtest_result_dict, 'CD_LAB_TEST_METH')
                                     # CD_LAB_TEST_CODE seems to be optional; if null in code list then .get results in False
                                     # e.g. for serotyping this field does not seem to be filled because there are no subtests
                                     and (not labtest_dict.get('CD_LAB_TEST_CODE') or labtest_dict.get('CD_LAB_TEST_CODE') == self.___get_value_by_capitalization_agnostic_key(labtest_result_dict, 'CD_LAB_TEST_CODE'))))

                if labtest_dict.get('code_list'):
                    data_translated[labtest_dict['translation']] = self._translation_codes['code_lists'][labtest_dict['code_list']][self.___cast_as_int_if_int(self.___get_value_by_capitalization_agnostic_key(labtest_result_dict, labtest_dict['value_field']))]
                else:
                    data_translated[labtest_dict['translation']] = self.___get_value_by_capitalization_agnostic_key(labtest_result_dict, labtest_dict['value_field'])

    @staticmethod
    def ___parse_complex_country_field(data_unprocessed: Dict[str, Any], data_translated: Dict[str, Any]) -> None:
        """
        Parses the optional infection country field list which didn't really fit in the main codes schema,
        e.g. "cd_infct_cntry": [{"cd_infct_cntry": "FR"}, {"cd_infct_cntry": "US"}]
        :param data_unprocessed: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :return: None
        """
        country_dicts_list: List[Dict[str, str]] = MainNominativeDataParserFromOds.___get_value_by_capitalization_agnostic_key(data_unprocessed, 'CD_INFCT_CNRTY')
        if country_dicts_list:
            for index, country_dict in enumerate(country_dicts_list):
                for key, value in country_dict.items():
                    data_translated[f"country_{index + 1}"] = value

    def ___parse_salmonella_symptom_fields(self, data_unprocessed: Dict[str, Any], data_translated: Dict[str, Any]) -> None:
        """
        Parses the mandatory symptom field list which didn't really fit in the main codes schema,
        e.g. "tx_ttl_symp": [{"cd_prob_nam": "25374005"}, {"cd_prob_nam": "91302008"}]
        :param data_unprocessed: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :return: None
        """
        symptom_list_of_dicts: List[Dict[str, str]] = self.___get_value_by_capitalization_agnostic_key(data_unprocessed, 'TX_TTL_SYMP')
        for symptom_dict in symptom_list_of_dicts:
            symptom_code = self.___get_value_by_capitalization_agnostic_key(symptom_dict, 'CD_PROB_NAM')
            symptom_code_translation = self._translation_codes['code_lists']['CD_PROB_NAM_codes'][self.___cast_as_int_if_int(symptom_code)]
            # todo these 5 symptom_ fields need to be added to the salmonella isolates table and the clinical_info field should be removed.
            data_translated[f"symptom_{symptom_code_translation.replace(' ', '_').lower()}"] = "Yes"

    @staticmethod
    def ___get_value_by_capitalization_agnostic_key(search_dictionary: Dict[str, Any], target_key: str) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """
        Searches a key capitalization agnostically in a dictionary because the ODS could not confirm that they were
        always going to send lower or uppercase keys.
        :param search_dictionary: the dictionary that should contain the target_key
        :param target_key: key that should capitalization agnostically be found in the search_dictionary
        :return: The value for the key lookup, or None if it isn't found.
        """
        if search_dictionary.get(target_key.lower()):
            return search_dictionary.get(target_key.lower())
        else:
            return search_dictionary.get(target_key.upper())

    @staticmethod
    def ___cast_as_int_if_int(possible_int: str) -> Union[int, str]:
        """
        In the code lists in yaml, keys are ints if they only consist of numbers.
        In order to be able to access the int keys, strings need to be cast as ints if they are.
        This function does exactly that.
        :param possible_int: string value
        :return: int if string contains only digits and str if not
        """
        if possible_int.isdigit():
            return int(possible_int)
        else:
            return possible_int

    def _move_files_according_to_success(self) -> None:
        """
        After having executed the entire rest of this script, move the files to the processed or error folder
        depending on the success of their parsing. If moved to the error folder, also add a log file.
        :return: None
        """
        for file in self._files_processed:
            self._sftp.rename(f'{self._base_sftp_dir}{file}', f'{self._base_sftp_dir}processed/{file}')
        for file in self._files_error:
            self._sftp.rename(f'{self._base_sftp_dir}{file}', f'{self._base_sftp_dir}error/{file}')
        for filename, contents in self._files_error_logs.items():
            error_log_filename = '.'.join(filename.split('.')[:-1]) + '.log'
            error_log_file = Path(self._temp_json_dir) / error_log_filename
            with error_log_file.open('w') as handle:
                handle.write(contents)
            self._sftp.put(str(error_log_file), f'{self._base_sftp_dir}error/{error_log_filename}')

    def __del__(self) -> None:
        """
        Closes the SSH and SFTP clients upon exit.
        :return: None
        """
        self._close_sftp_connection(self._ssh, self._sftp)


if __name__ == '__main__':
    # run main
    MainNominativeDataParserFromOds()
