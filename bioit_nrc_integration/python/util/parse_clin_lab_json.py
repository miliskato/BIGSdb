import abc
import math
from datetime import datetime
from typing import Any, Literal, Optional, Union


class ParseClinLabJson(object, metaclass=abc.ABCMeta):
    """
    MetaClass to parse a Json DCD file (CLIN or LAB)
    """
    def __init__(self, data_unprocessed: dict[str, Any], filetype: Literal['CLIN', 'LAB'], species: str,
                 translation_codes: dict[str, Any]) -> None:
        """
        This class can parse and translate an incoming unprocces CLIN or LAB DCD file from the ODS using the
        main 'run' function.
        :param data_unprocessed: original unprocessed data
        :param filetype: CLIN or LAB
        :param species: commonly used bioit species name: either genus or specific like stec
        :param translation_codes: translation codes from the nominative ODS configuration file
        :return: None
        """
        self._data_unprocessed = data_unprocessed
        self._filetype = filetype
        self._species = species
        self._translation_codes = translation_codes

        self._data_translated = {}

    def run(self) -> dict[str, Any]:
        """
        Public class function to execute both the common and pathogen specific parsing code.
        The pathogen specific code needs to run after the common code because it can use values that were returned by
        the common code.
        :return: the translated dictionary to be inserted into MongoDB.
        """
        self._execute_common_code()
        self._execute_pathogen_specific_code()
        return self._data_translated

    def _execute_common_code(self) -> None:
        """
        Executes the parsing code that is common between all pathogens.
        :return: None
        """
        if self._filetype == 'LAB':
            self.__calculate_age_fields()
            self.__parse_complex_labtest_results()
        if self._filetype == 'CLIN':
            self.__parse_complex_country_field()
        # loop over schema
        for hd_key, hd_key_property_dict in self._translation_codes['schema'][self._filetype].items():
            unprocessed_value = self.___get_value_by_capitalization_agnostic_key(self._data_unprocessed, hd_key)
            if unprocessed_value:
                if hd_key_property_dict.get('code_list'):
                    value = self._translation_codes['code_lists'][hd_key_property_dict['code_list']][
                        self.___cast_as_int_if_int(unprocessed_value)]
                    if hd_key_property_dict.get('other') and value == 'Other':
                        value = self.___get_value_by_capitalization_agnostic_key(self._data_unprocessed, hd_key_property_dict['other'])
                else:
                    value = unprocessed_value
                self._data_translated[hd_key_property_dict['translation']] = value
            else:
                if hd_key_property_dict['required'] is False:
                    if hd_key_property_dict.get('default'):
                        self._data_translated[hd_key_property_dict['translation']] = hd_key_property_dict['default']
                elif isinstance(hd_key_property_dict['required'], list) and self._species not in hd_key_property_dict['required']:
                    pass
                else:
                    raise Exception(f"key {hd_key} is missing but is required in {self._filetype} file!!")
        # add id to be able to find in MongoDB
        self._data_unprocessed['_id'] = self._data_translated['_id']  # data_translated['_id'] == data_unprocessed['TX_BUSINESS_KEY']

    @abc.abstractmethod
    def _execute_pathogen_specific_code(self) -> None:
        """
        Abstract method that needs to be configured in every pathogen class separately.
        :return: None
        """
        pass

    def __calculate_age_fields(self) -> None:
        """
        Calculates the two age fields patient_age and patient_age_group from the DOB and the collection date.
        :return: None
        """
        # DOB is not a mandatory field so it can be missing = None
        dob = self.___get_value_by_capitalization_agnostic_key(self._data_unprocessed, 'DT_PAT_DOB')
        collection_date = self.___get_value_by_capitalization_agnostic_key(self._data_unprocessed, 'DT_LAB_COLLCN')
        if dob and dob != '1900-01-01' and collection_date:
            # Calculate the number of years
            # Average year length considering leap years = 365.25 days
            patient_age = math.floor((datetime.strptime(collection_date, "%Y-%m-%dT%H:%M:%S") -
                                      datetime.strptime(dob, "%Y-%m-%d")).days / 365.25)
            if patient_age < -1:
                # in Salmonella test unknowns for patient_age and patient_age_group are encoded as UNK
                self._data_translated['patient_age'] = 'UNK'
                self._data_translated['patient_age_group'] = 'UNK'
                pass
            self._data_translated['patient_age'] = patient_age
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
            self._data_translated['patient_age_group'] = next(
                (group for group, start, end in age_groups if start <= patient_age <= end))
        else:
            # in Salmonella test unknowns for patient_age and patient_age_group are encoded as UNK
            self._data_translated['patient_age'] = 'UNK'
            self._data_translated['patient_age_group'] = 'UNK'

    def __parse_complex_labtest_results(self) -> None:
        """
        Parses the labtest results from a complex list of dictionaries.
        For quantitative results, it is apparently not important to also add the unit, these are therefore ignored.
        e.g. "tx_ttl_lab_test": [{"dt_lab_test": "2024-03-25T12:00:00",  "tx_lab_rr_ll": "ref low",  "tx_lab_rr_ul": "ref up",  "cd_lab_pnl_batt": "385432009",  "cd_lab_rslt_sta": "corrected",  "cd_lab_reslt_tpe": "19851009",  "cd_lab_rslt_flag": "260405006",  "cd_lab_test_code": "468-9",  "cd_lab_test_meth": "14788002",  "ms_lab_rr_ll_val": 11.00000,  "ms_lab_rr_ul_val": 150.00000,  "cd_lab_rr_ll_unit": "385432009",  "cd_lab_rr_ul_unit": "385432009",  "cd_lab_intrpr_meth": "261665006",  "tx_lab_rslt_intrpr": "Test 3 interpretation",  "tx_lab_test_rslt_id": "Test Result 3",  "cd_lab_test_rslt_sta": "preliminary",  "tx_lab_cmnt_test_rslt": "Lab Test 3 comment",  "ms_lab_test_rslt_qn_val": 99.00000,  "cd_lab_test_rslt_qn_unit": "385432009"}, {"dt_lab_test": "2024-02-06T12:00:00",  "tx_lab_rr_ll": "lower limit",  "tx_lab_rr_ul": "Ref upper Range",  "cd_lab_pnl_batt": "385432009",  "cd_lab_rslt_sta": "registered",  "cd_lab_reslt_tpe": "252275004",  "cd_lab_rslt_flag": "281300000",  "cd_lab_test_code": "TC0031",  "cd_lab_test_meth": "363779003",  "ms_lab_rr_ll_val": 55.00000,  "ms_lab_rr_ul_val": 66.00000,  "cd_lab_rr_ll_unit": "385432009",  "cd_lab_rr_ul_unit": "385432009",  "cd_lab_intrpr_meth": "IM0001",  "tx_lab_rslt_intrpr": "Res Interpretation",  "cd_lab_test_rslt_ql": "83185005",  "tx_lab_test_rslt_id": "TestResID",  "cd_lab_test_rslt_sta": "preliminary",  "tx_lab_cmnt_test_rslt": "Lab Test comment"}]
        :return: None
        """
        labtest_list_of_result_dicts = self.___get_value_by_capitalization_agnostic_key(self._data_unprocessed, 'TX_TTL_LAB_TEST')
        # The mic_resistances field should be a string concatenation of all resistant antibiotics. All resistant ones will
        # be stored in the mic_resistances_list, ordered alphabetically and concatenated with spaces in between.
        mic_resistances_list: list[str] = []
        if labtest_list_of_result_dicts:
            labtest_code_combinations = self._translation_codes['code_lists']['TX_TTL_LAB_TEST_combinations']
            for labtest_result_dict in labtest_list_of_result_dicts:
                labtest_code_combination = next((
                    labtest_code_combination for labtest_code_combination in labtest_code_combinations if
                    labtest_code_combination['CD_LAB_TEST_CODE'] == self.___get_value_by_capitalization_agnostic_key(
                        labtest_result_dict, 'CD_LAB_TEST_CODE')))
                translation = labtest_code_combination['translation']

                if labtest_code_combination.get('code_list'):
                    # Even if the field's value supposedly needs to come from a code list, there can be exceptions
                    # where it doesn't. E.g. it is impossible to list all serotype formulas, and new ones keep being
                    # added. The following if else catches these exceptions.
                    code_value = self.___cast_as_int_if_int(self.___get_value_by_capitalization_agnostic_key(
                        labtest_result_dict, labtest_code_combination['value_field']))
                    if code_value:
                        self._data_translated[translation] = self._translation_codes['code_lists'][labtest_code_combination['code_list']][code_value]
                        if translation.startswith('mic_') and \
                                translation.endswith('_I') and \
                                self._data_translated[translation] == 'Resistant':
                            mic_resistances_list.append((translation.split('_'))[1])
                    else:
                        self._data_translated[translation] = \
                            self.___get_value_by_capitalization_agnostic_key(labtest_result_dict, 'TX_LAB_TEST_RSLT_TXT')
                else:
                    self._data_translated[translation] = \
                        self.___get_value_by_capitalization_agnostic_key(
                            labtest_result_dict, labtest_code_combination['value_field'])
            if mic_resistances_list:
                mic_resistances_list.sort()
                self._data_translated['mic_resistances'] = ' '.join([resistance for resistance in mic_resistances_list])

    def __parse_complex_country_field(self) -> None:
        """
        Parses the optional infection country field list which didn't really fit in the main codes schema,
        e.g. "cd_infct_cntry": [{"cd_infct_cntry": "FR"}, {"cd_infct_cntry": "US"}]
        :return: None
        """
        country_dicts_list: list[dict[str, str]] = self.___get_value_by_capitalization_agnostic_key(
            self._data_unprocessed, 'CD_INFCT_CNRTY')
        if country_dicts_list:
            for index, country_dict in enumerate(country_dicts_list):
                for key, value in country_dict.items():
                    self._data_translated[f"country_{index + 1}"] = value

    def ___parse_repeat_fields(self, repeat_field_name: str, field_name: str, code_list_name: str, bigsdb_prefix: str,
                               other: str = None) -> None:
        """
        Parses the mandatory repeat field lists which didn't really fit in the main codes schema,
        e.g. "tx_ttl_symp": [{"cd_prob_nam": "25374005"}, {"cd_prob_nam": "91302008"}]
        :param repeat_field_name: the key name of the repeat field in the DCD
        :param field_name: the key name of the value in the dictionary in the repeat field's list
        :param code_list_name: the name of the code list in the config file
        :param bigsdb_prefix: the prefix used for the concatenation of the field
        :param other: if the translated value of field_name is 'Other', parse this text field to get the value of 'Other'.
        Implemented originally for the CD_PROB_NAM_CHLD & CD_PROB_NAM_ADLT fields in Listeria. These are repeat fields,
        but the value should only be filled once according to Florian. If it were to be filled more than once after all,
        the code would take the last occurrence.
        :return: None
        """
        repeat_list_of_dicts: list[dict[str, str]] = self.___get_value_by_capitalization_agnostic_key(
            self._data_unprocessed, repeat_field_name)
        for symptom_dict in repeat_list_of_dicts:
            symptom_code = self.___get_value_by_capitalization_agnostic_key(symptom_dict, field_name)
            symptom_code_translation = self._translation_codes['code_lists'][code_list_name][self.___cast_as_int_if_int(symptom_code)]
            self._data_translated[f"{bigsdb_prefix}_{symptom_code_translation.replace(' ', '_').lower()}"] = "Yes"
            if other and symptom_code_translation == 'Other':
                other_value = self.___get_value_by_capitalization_agnostic_key(symptom_dict, other)
                self._data_translated[f"{bigsdb_prefix}_{symptom_code_translation.replace(' ', '_').lower()}"] = other_value

    @staticmethod
    def ___get_value_by_capitalization_agnostic_key(search_dictionary: dict[str, Any], target_key: str) -> Optional[Union[dict[str, Any], list[Any], str]]:
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
