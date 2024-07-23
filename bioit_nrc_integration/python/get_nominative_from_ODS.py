import json
import logging
import math
import socket
import sys
import tempfile
import traceback
import yaml
from datetime import datetime
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

                        if filetype == 'LAB':
                            self.__calculate_age_fields(data, data_translated)
                            self.__parse_complex_labtest_results()
                        if filetype == 'CLIN':
                            self.__parse_complex_country_field(data, data_translated)
                        # loop over schema
                        for hd_key, hd_key_property_dict in self._translation_codes['schema'][filetype]:
                            # Get value capitalisation agnostically
                            unprocessed_value = data.get(hd_key.lower()) if data.get(hd_key.lower()) else data.get(hd_key)
                            if unprocessed_value:
                                if hd_key_property_dict.get('code_list'):
                                    value = self._translation_codes['code_lists'][hd_key_property_dict['code_list']][unprocessed_value]
                                else:
                                    value = unprocessed_value
                                data_translated[hd_key_property_dict['translation']] = value
                            else:
                                if hd_key_property_dict['required'] is False:
                                    if hd_key_property_dict.get('default'):
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

    @staticmethod
    def __calculate_age_fields(data, data_translated) -> None:
        """
        Calculates the two age fields patient_age and patient_age_group from the DOB and the collection date.
        :param data: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :return: None
        """
        # DOB is not a mandatory field so it can be missing
        if data.get('DT_PAT_DOB'.lower()):
            # Calculate the number of years
            # Average year length considering leap years = 365.25 days
            patient_age = math.floor((datetime.strptime(data['DT_LAB_COLLCN'.lower()], "%Y-%m-%dT%H:%M:%S") -
                                      datetime.strptime(data['DT_PAT_DOB'.lower()], "%Y-%m-%d")).days / 365.25)
            data_translated['patient_age'] = patient_age
            age_groups = [
                ("1 and below", 0, 1),
                ("Between 2 and 4", 2, 4),
                ("Between 5 and 9", 5, 9),
                ("Between 10 and 14", 10, 14),
                ("Between 15 and 19", 15, 19),
                ("Between 20 and 24", 20, 24),
                ("Between 25 and 44", 25, 44),
                ("Between 45 and 64", 45, 64),
                ("65 and above", 64, 150)
            ]
            data_translated['patient_age_group'] = next(
                (group for group, start, end in age_groups if start <= patient_age <= end))
        else:
            # in Salmonella test unknowns for patient_age and patient_age_group are encoded as UNK
            data_translated['patient_age'] = 'UNK'
            data_translated['patient_age_group'] = 'UNK'

    def __parse_complex_labtest_results(self, data, data_translated) -> None:
        """
        Parses the
        e.g. "tx_ttl_lab_test": [{"dt_lab_test": "2024-03-25T12:00:00",  "tx_lab_rr_ll": "ref low",  "tx_lab_rr_ul": "ref up",  "cd_lab_pnl_batt": "385432009",  "cd_lab_rslt_sta": "corrected",  "cd_lab_reslt_tpe": "19851009",  "cd_lab_rslt_flag": "260405006",  "cd_lab_test_code": "468-9",  "cd_lab_test_meth": "14788002",  "ms_lab_rr_ll_val": 11.00000,  "ms_lab_rr_ul_val": 150.00000,  "cd_lab_rr_ll_unit": "385432009",  "cd_lab_rr_ul_unit": "385432009",  "cd_lab_intrpr_meth": "261665006",  "tx_lab_rslt_intrpr": "Test 3 interpretation",  "tx_lab_test_rslt_id": "Test Result 3",  "cd_lab_test_rslt_sta": "preliminary",  "tx_lab_cmnt_test_rslt": "Lab Test 3 comment",  "ms_lab_test_rslt_qn_val": 99.00000,  "cd_lab_test_rslt_qn_unit": "385432009"}, {"dt_lab_test": "2024-02-06T12:00:00",  "tx_lab_rr_ll": "lower limit",  "tx_lab_rr_ul": "Ref upper Range",  "cd_lab_pnl_batt": "385432009",  "cd_lab_rslt_sta": "registered",  "cd_lab_reslt_tpe": "252275004",  "cd_lab_rslt_flag": "281300000",  "cd_lab_test_code": "TC0031",  "cd_lab_test_meth": "363779003",  "ms_lab_rr_ll_val": 55.00000,  "ms_lab_rr_ul_val": 66.00000,  "cd_lab_rr_ll_unit": "385432009",  "cd_lab_rr_ul_unit": "385432009",  "cd_lab_intrpr_meth": "IM0001",  "tx_lab_rslt_intrpr": "Res Interpretation",  "cd_lab_test_rslt_ql": "83185005",  "tx_lab_test_rslt_id": "TestResID",  "cd_lab_test_rslt_sta": "preliminary",  "tx_lab_cmnt_test_rslt": "Lab Test comment"}]
        :param data: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :return: None
        """
        labtest_list_of_result_dicts = data.get('TX_TTL_LAB_TEST'.lower())
        if labtest_list_of_result_dicts:
            for labtest_result_dict in labtest_list_of_result_dicts:
                labtest_result_combinations = self._translation_codes['code_lists']['TX_TTL_LAB_TEST_combinations']
                labtest_dict = next((labtest_dict for labtest_dict in labtest_result_combinations if
                                     # CD_LAB_TEST_METH is mandatory I believe
                                     labtest_dict['CD_LAB_TEST_METH'] == labtest_result_dict.get('CD_LAB_TEST_METH'.lower())
                                     # CD_LAB_TEST_CODE seems to be optional; if '' in code list then .get results in False
                                     # e.g. for serotyping this field does not seem to be filled because there are no subtests
                                     and labtest_dict.get('CD_LAB_TEST_CODE') and
                                     labtest_dict['CD_LAB_TEST_CODE'] == labtest_result_dict.get('CD_LAB_TEST_CODE'.lower())))

                if labtest_dict.get('code_list'):
                    data_translated[labtest_dict['translation']] = self._translation_codes['code_lists'][labtest_dict['code_list']][labtest_result_dict[labtest_dict['value_field'.lower()]]]
                else:
                    data_translated[labtest_dict['translation']] = labtest_result_dict.get(labtest_dict['value_field'].lower())

    @staticmethod
    def __parse_complex_country_field(data, data_translated) -> None:
        """
        Parses the optional infection country field list which didn't really fit in the main codes schema,
        e.g. "cd_infct_cntry": [{"cd_infct_cntry": "130337"}, {"cd_infct_cntry": "130328"}]
        :param data: original unprocessed data
        :param data_translated: translated data to be inserted in MongoDB to be inserted in BIGSdb
        :return: None
        """
        country_dicts_list = data.get('CD_INFCT_CNRTY'.lower())
        if country_dicts_list:
            for index, country_dict in enumerate(country_dicts_list):
                for key, value in country_dict:
                    data_translated[f"country_{index + 1}"] = value  # todo possibly translate using missing codelist

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
