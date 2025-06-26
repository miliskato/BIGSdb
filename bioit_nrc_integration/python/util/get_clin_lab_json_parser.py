from typing import Type

from .parse_clin_lab_json import ParseClinLabJson
from .parse_clin_lab_json_influenza import ParseClinLabJsonInfluenza
from .parse_clin_lab_json_listeria import ParseClinLabJsonListeria
from .parse_clin_lab_json_salmonella import ParseClinLabJsonSalmonella


def get_clin_lab_json_parser(species: str) -> Type[ParseClinLabJson]:
    """
    Selects the correct pathogen specific CLIN/LAB JSON parser class and returns it.
    If there is no species-specific parser, the base class is used.
    :param species: commonly used bioit species name: either genus or specific like stec
    :return: ParseClinLabJson
    """
    for parser in [ParseClinLabJsonInfluenza, ParseClinLabJsonListeria, ParseClinLabJsonSalmonella]:
        if species == parser.TARGET_SPECIES:
            return parser
    return ParseClinLabJson
