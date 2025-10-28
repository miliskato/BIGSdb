from typing import Any, Literal

from .parse_clin_lab_json import ParseClinLabJson


class ParseClinLabJsonMycobacterium(ParseClinLabJson):
    """
    Mycobacterium-specific class to parse a Json DCD file (CLIN or LAB)
    """
    TARGET_SPECIES = 'mycobacterium'

    def __init__(self, data_unprocessed: dict[str, Any], filetype: Literal['CLIN', 'LAB'], species: str,
                 translation_codes: dict[str, Any], dtap: Literal['dev', 'test', 'acc', 'prod']) -> None:
        """
        Initializes this class by initializing the super class
        :param data_unprocessed: original unprocessed data
        :param filetype: CLIN or LAB
        :param species: commonly used bioit species name: either genus or specific like stec
        :param translation_codes: translation codes from the nominative ODS configuration file
        :param dtap: current DTAP environment
        :return: None
        """
        super().__init__(data_unprocessed, filetype, species, translation_codes, dtap)

    def _execute_pathogen_specific_code(self) -> None:
        """
        This function executes the Mycobacterium specific DCD parsing code.
        :return: None
        """
        if self._filetype == 'LAB':
            pass
        elif self._filetype == 'CLIN':
            self.__get_physician_name()

    def __get_physician_name(self) -> None:
        """
        Gets the physician name if it is present in the DCD based on logic discussed with Florian.
        :return: None
        """
        last_name = self._get_value_by_capitalization_agnostic_key(self._data_unprocessed, 'TX_HP_LAST_NAME')
        if last_name:
            self._data_translated['physician_name'] = last_name
            first_name = self._get_value_by_capitalization_agnostic_key(self._data_unprocessed, 'TX_HP_FIRST_NAM')
            if first_name:
                self._data_translated['physician_name'] += f' {first_name}'
