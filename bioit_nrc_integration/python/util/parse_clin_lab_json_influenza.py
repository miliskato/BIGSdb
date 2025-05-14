from datetime import datetime
from typing import Any, Literal

from .parse_clin_lab_json import ParseClinLabJson


class ParseClinLabJsonInfluenza(ParseClinLabJson):
    """
    Influenza-specific class to parse a Json DCD file (CLIN or LAB)
    """
    TARGET_SPECIES = 'influenza'
    FLU_TESTS = {'34487-9': 'A', '40982-1': 'B'}
    HA_TESTS = {'49521-8': 'H1', '55465-9': 'H1', '57985-4': 'H2', '49524-2': 'H3', 'TC0004': 'H4', '38272-1': 'H5',
                 '38271-3': 'H6', '38270-5': 'H7', 'TC0005': 'H8', '49528-3': 'H9', 'TC0006': 'H10', 'TC0007': 'H11',
                 'TC0008': 'H12', 'TC0009': 'H13', 'TC0010': 'H14', 'TC0011': 'H15', 'TC0012': 'H16', 'TC0013': 'H17',
                 'TC0014': 'H18'}
    NA_TESTS = { '99623-1': 'N1', 'TC0015': 'N2', 'TC0016': 'N3', 'TC0017': 'N4', 'TC0018': 'N5', 'TC0019': 'N6',
                 'TC0020': 'N7', 'TC0021': 'N8', 'TC0022': 'N9', 'TC0023': 'N10', 'TC0024': 'N11' }
    B_TESTS = { '74785-7': 'VIC', '74786-5': 'YAM'}

    def __init__(self, data_unprocessed: dict[str, Any], filetype: Literal['CLIN', 'LAB'], species: str,
                 translation_codes: dict[str, Any]) -> None:
        """
        Initializes this class by initializing the super class
        :param data_unprocessed: original unprocessed data
        :param filetype: CLIN or LAB
        :param species: commonly used bioit species name: either genus or specific like stec
        :param translation_codes: translation codes from the nominative ODS configuration file
        :return: None
        """
        super().__init__(data_unprocessed, filetype, species, translation_codes)

    def _execute_pathogen_specific_code(self) -> None:
        """
        This function executes the Influenza specific DCD parsing code.
        :return: None
        """
        if self._filetype == 'LAB':
            self.__extract_sari_hospi_ili()
            self.__decompose_date_fields()
        elif self._filetype == 'CLIN':
            self.__get_type_info()

    def __extract_sari_hospi_ili(self) -> None:
        """
        Exctracts whether the sample is HOSPI, ILI, or SARI from the internal reference sample id if it is present.
        :return: None
        """
        internal_reference_sample_id = self.___get_value_by_capitalization_agnostic_key(self._data_unprocessed, 'TX_INT_ID')
        case_type = 'Unknown'
        if internal_reference_sample_id:
            if 'IH' in internal_reference_sample_id:
                case_type = 'HOSPI'
            elif 'IG' in internal_reference_sample_id:
                case_type = 'ILI'
            elif 'IS' in internal_reference_sample_id:
                case_type = 'SARI'

        self._data_translated['case_type'] = case_type

    def __decompose_date_fields(self) -> None:
        """
        For certain Influenza date fields, the date needs to be decomposed into day, month, year (and week).
        This function does that.
        :return: None
        """
        for date_field in ['vaccination_date', 'antiviral_treatment_date', 'sampling_date']:
            present = self._data_translated.get(date_field)
            if present:
                date_object = datetime.strptime(present.split('T')[0], "%Y-%m-%d")
                self._data_translated[date_field.replace('date', 'day')] = date_object.day
                self._data_translated[date_field.replace('date', 'month')] = date_object.month
                self._data_translated[date_field.replace('date', 'year')] = date_object.year
                if date_field == 'sampling_date':
                    self._data_translated[date_field.replace('date', 'week')] = date_object.isocalendar().week

    def __get_type_info(self) -> None:
        """
        The PCR subtype is spread over 30 different fields for influenza A and 2 for influenza B.
        There is no summary field. This function generates the summary.
        :return: None
        """
        self._data_translated['Flu_type'] = self.___get_type_part(self.FLU_TESTS)

        ha = self.___get_type_part(self.HA_TESTS)
        na = self.___get_type_part(self.NA_TESTS)
        b = self.___get_type_part(self.B_TESTS)
        if ha:
            self._data_translated['FluA_SubtypeHAPCR'] = ha
            self._data_translated['FluA_subtypePCR'] = ha + na
        elif na:
            self._data_translated['FluA_SubtypeNAPCR'] = na
            self._data_translated['FluA_subtypePCR'] = ha + na
        elif b:
            self._data_translated['FluB_lineagePCR'] = b

    def ___get_type_part(self, code_list: dict[str, str]) -> str:
        """
        For a given code list, checks if any of the test codes are present and if their value is 'Detected'.
        Returns the first value it encounters. If none are encountered, an empty string is returned.
        :param code_list: list of codes to check and the translated values
        :return: a single value from the code list or an empty string
        """
        labtest_list_of_result_dicts = self.___get_value_by_capitalization_agnostic_key(self._data_unprocessed,
                                                                                        'TX_TTL_LAB_TEST')
        if not labtest_list_of_result_dicts:
            return ''
        for code, value in code_list:
            result_dict = next((
                result_dict for result_dict in labtest_list_of_result_dicts if
                code == self.___get_value_by_capitalization_agnostic_key(
                    result_dict, 'CD_LAB_TEST_CODE')))
            if self.___cast_as_int_if_int(self.___get_value_by_capitalization_agnostic_key(result_dict, 'CD_LAB_TEST_RSLT_QL')) == 260373001:
                # if detected
                return value
        return ''
