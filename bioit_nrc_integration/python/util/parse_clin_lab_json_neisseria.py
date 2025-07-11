from typing import Any, Literal

from .parse_clin_lab_json import ParseClinLabJson


class ParseClinLabJsonNeisseria(ParseClinLabJson):
    """
    Neisseria-specific class to parse a Json DCD file (CLIN or LAB)
    """
    TARGET_SPECIES = 'neisseria'

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
        This function executes the Neisseria specific DCD parsing code.
        :return: None
        """
        if self._filetype == 'LAB':
            pass
        elif self._filetype == 'CLIN':
            pass
