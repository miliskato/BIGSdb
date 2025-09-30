import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.model.json_model import MongoRecordDict
from bioit_mongodb_scripts.util.python_utility_functions import access_value_in_dict_using_list_as_dictpath
from bioit_nrc_integration.python.config import CODES_GENOMIC_ODS
from bioit_nrc_integration.python.util.python_utility_functions import send_dictionary_to_ods
from bioit_nrc_integration.python.util.sftp_connection_ods import SFTPConnectionODS

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


class SendGenomicToODS:
    """
    Class to get all required values for a pathogen from a MongoDB document and
    to send these values as a JSON file to the ODS over SFTP.
    """
    def __init__(self, document: MongoRecordDict, species: str, upload_path: str) -> None:
        """
        Initialises this class and executes the main function.
        :param document: MongoDB document for a single sample.
        :param species: commonly used bioit species name: either genus or specific like stec.
        :param upload_path: The upload path
        :return: None
        """
        self._document = document
        self._species = species

        # get HD ODS dictionaries to be able to translate to usable text
        with CODES_GENOMIC_ODS.open('r') as handle:
            self._translation_codes = yaml.safe_load(handle)

        with SFTPConnectionODS('send') as self._sftp_connection_ods:

            self._output_json_dict = self._create_output_json_dict()

            send_dictionary_to_ods(self._output_json_dict, self._sftp_connection_ods.sftp, upload_path)

    def _create_output_json_dict(self) -> dict[str, Any]:
        """
        Finds the required values for the ODS in the document and puts them in a dictionary with the right format.
        :return: output dictionary in the right format ready to be sent to the ODS
        """
        data_dict = {}
        for variable, variable_info in self._translation_codes['common'].items():
            data_dict[variable] = access_value_in_dict_using_list_as_dictpath(variable_info['dict_path'],
                                                                              dict(self._document))
        # although the DT_PIPELINE_ANAL is common, it can not be processed regularly using
        # the previous function because it needs to be converted
        data_dict['DT_PIPELINE_ANAL'] = datetime.strptime(self._document['results']['analysis_date'],
                                                          '%d/%m/%Y - %X').strftime('%Y-%m-%dT%X')

        if self._translation_codes.get(self._species):
            for variable, variable_info in self._translation_codes[self._species].items():
                if variable_info.get('custom'):
                    self.__parse_custom_results(variable_info, data_dict)
                else:
                    data_dict[variable] = access_value_in_dict_using_list_as_dictpath(variable_info['dict_path'],
                                                                                      dict(self._document))
                    if variable_info.get('code_list'):
                        data_dict[variable] = self._translation_codes['code_lists'][
                            variable_info['code_list']][data_dict[variable]]
            if self._species == 'influenza':
                self.__add_influenza_a_ha_na_info(data_dict)
        return {'metadata': {key: value for key, value in self._translation_codes['pathogens'][self._species].items()},
                'data': data_dict}

    @staticmethod
    def __add_influenza_a_ha_na_info(data_dict: dict[str, Any]) -> None:
        """
        Checks if the pathogen is influenza A, then checks if the Type matches HxNx, and if it does, splits HxNx into Hx
        and Nx and adds these to their corresponding variables in the data dictionary to be sent.
        :param data_dict: the data dictionary to send to the ODS, to be modified in place.
        :return: None
        """
        if data_dict['TX_GENTPE_TPE'] == 'A':
            match = re.match(r"^H(\d+)N(\d+)$", data_dict['TX_GENTPE_SUBTPE'])
            if match:
                data_dict['TX_GENTPE_SUBTPE_HEMAG'] = f"H{match.group(1)}"
                data_dict['TX_GENTPE_SUBTPE_NEURAM'] = f"N{match.group(2)}"

    def __parse_custom_results(self, variable_info, data_dict: dict[str, Any]) -> None:
        """
        Wrapper function to parse genomic results in a custom manner.
        :param variable_info: the current variable's info
        :param data_dict: the data dictionary to send to the ODS, to be modified in place.
        :return: None
        """
        if variable_info['custom'] == 'resfinder4':
            self.__parse_custom_results_resfinder4(variable_info, data_dict)
        else:
            raise NotImplementedError(f"Custom parsing method {variable_info['custom']} not implemented.")

    def __parse_custom_results_resfinder4(self, variable_info, data_dict: dict[str, Any]) -> None:
        """
        Parses the results of ResFinder4 in a custom manner. The antibiotic phenotypes are stored in a 'Phenotype' field
        in dictionaries in a list. The Phenotype field can store one or multiple comma separated values, but the
        formatting of the comma separation is not always consistent. This code tries to clean up the inconsistencies,
        and then for every unique antibiotic, adds a 'Resistant' value to the output data dictionary.
        :param variable_info: the current variable's info
        :param data_dict: the data dictionary to send to the ODS, to be modified in place.
        :return: None
        """
        hits: list[dict[str, Any]] = access_value_in_dict_using_list_as_dictpath(variable_info['dict_path'],
                                                                                 dict(self._document))
        phenotypes = set([hit['Phenotype'] for hit in hits])
        antibiotics = []
        for phenotype in phenotypes:
            antibiotics.extend(phenotype.split(','))
        antibiotics_reformatted = set([antibiotic.lower().replace(' ', '') for antibiotic in antibiotics])
        for antibiotic in antibiotics_reformatted:
            antibiotic_code = self._translation_codes['custom']['resfinder4'].get(antibiotic)
            # Ignore potential new antibiotics that are not in DCD
            if antibiotic_code:
                # Add Resistant info, don't add Susceptible info because ResFinder only gives info about resistances and
                # not about susceptibilities.
                data_dict[antibiotic_code] = self._translation_codes['code_lists']['SRI']['Resistant']
