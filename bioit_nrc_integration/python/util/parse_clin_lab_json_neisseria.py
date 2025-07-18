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
            self.__choose_serogroup_pheno()
        elif self._filetype == 'CLIN':
            self._parse_repeat_fields('TX_TTL_PROB_NAM_REPEAT', 'CD_PROB_NAM', 'CD_PROB_NAM_codes', 'symptom')

    def __choose_serogroup_pheno(self) -> None:
        """
        Picks the serogroup_pheno based on logic that Florian sent through mail:
        serogroup_agglutination > serogroup_pcr
        The information below was not discussed with Florian but implemented as such because it seems logical:
        In the neisseria codes multiple culture-related fields are present; 'no growth', 'autoagglutinable', ..
        In order to not save these as the final serogroup_pheno, a check is performed that 'meni' is present in the value.
        Then again there is a value 'Neisseria meningitidis non-groupable', if the serogroup_agglutination reports this,
        and the serogroup_pcr reports an actual serogroup, then the serogroup_agglutination will take precedency anyway.
        :return: None
        """
        for serovar_type in ['serogroup_agglutination', 'serogroup_pcr']:
            if self._data_translated.get(serovar_type) and 'meni' in self._data_translated[serovar_type]:
                self._data_translated['serogroup_pheno'] = self._data_translated[serovar_type]
                break
