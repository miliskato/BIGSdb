from typing import Any, Literal

from .parse_clin_lab_json import ParseClinLabJson


class ParseClinLabJsonSalmonella(ParseClinLabJson):
    """
    Salmonella-specific class to parse a Json DCD file (CLIN or LAB)
    """
    TARGET_SPECIES = 'salmonella'

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
        This function executes the Salmonella specific DCD parsing code.
        :return: None
        """
        if self._filetype == 'LAB':
            self.__choose_serovar_final()
        elif self._filetype == 'CLIN':
            self.___parse_repeat_fields('TX_TTL_SYMP_REPEAT', 'CD_PROB_NAM', 'CD_PROB_NAM_codes', 'symptom')

    def __choose_serovar_final(self) -> None:
        """
        Picks the serovar_final based on logic that Florian sent through mail:
        serovar_luminex > serovar_agglutination > malditof_identification
        :return: None
        """
        for serovar_type in ['serovar_luminex', 'serovar_agglutination', 'malditof_identification']:
            if self._data_translated.get(serovar_type):
                self._data_translated['serovar_final'] = self._data_translated[serovar_type]
                break
