import argparse
import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Dict, Final, List, Tuple

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblProfiles, TblProfileFields, TblProfileMembers, TblSequences
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
# For this script I am assuming that profiles do not retire.

PROFILE_FILE: Final[str] = 'profiles.tsv'


def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str,
                                 choices=specieslist, default=specieslist,
                                 nargs='+')  # this does allow for the same species multiple times but doesnt really matter, theyre uniquely filtered using set()
    return argument_parser.parse_args()

# three tables are important:

# 1. profiles:
#  scheme_id | profile_id | sender | curator | date_entered | datestamp
# -----------+------------+--------+---------+--------------+------------
#          1 | 1          |      1 |       1 | 2022-03-03   | 2022-03-03

# 2. profile_fields:
#  scheme_id | scheme_field | profile_id | value | curator | datestamp
# -----------+--------------+------------+-------+---------+------------
#          1 | testextra    | 1          | GZ5   |       1 | 2022-03-03
#          1 | ST           | 1          | 1     |       1 | 2022-03-03

# 3. profile_members:
#  scheme_id | locus | profile_id | allele_id | curator | datestamp
# -----------+-------+------------+-----------+---------+------------
#          1 | aroC  | 1          | 1         |       1 | 2022-03-03
#          1 | dnaN  | 1          | 1         |       1 | 2022-03-03
#          1 | hemD  | 1          | 1         |       1 | 2022-03-03
#          1 | hisD  | 1          | 5         |       1 | 2022-03-03
#          1 | purE  | 1          | 6         |       1 | 2022-03-03
#          1 | sucA  | 1          | 8         |       1 | 2022-03-03
#          1 | thrA  | 1          | 4         |       1 | 2022-03-03
#


def __insert_profiles(scheme: str, schemedict: Dict[str, Dict[str, str]], indexdict: Dict[str, int], profile_line_dict: Dict[str, str],
                      list_to_be_inserted: set, seqdef_profiles_psql_tbl: TblProfiles, species: str) -> None:
    """
    Inserts profiles for a given scheme in a given species database (seqdef_profiles_psql_table)
    :param scheme: the currently iterating scheme
    :param schemedict: dictionary containing scheme metadata
    :param indexdict: dictionary containing profile locus indexes, and profile fields indexes in the tsv profiles file
    :param profile_line_dict: dictionary of main numeric profile fields (often ST) and their corresponding lines in the tsv
    :param list_to_be_inserted: list of main numeric profile fields (often ST) to be inserted
    :param seqdef_profiles_psql_tbl: seqdef profiles table/ connection instance for a given species
    :param species: commonly used bioit species name: either genus or specific like stec
    :return: None
    """
    # since we only need one db per scheme, it can stay open during the entire definition
    for profile in list_to_be_inserted:
        # first table (profiles):
        seqdef_profiles_psql_tbl.insert_profile((schemedict[scheme]['schemename_bigsdb'], profile))
        profiles_to_be_removed = set()
        # second table (profile fields):
        with TblProfileFields(species) as seqdef_profilefields_psql_table:
            for field in schemedict[scheme]['scheme_fields']:
                line: str = profile_line_dict[profile].replace('? ', '').replace('Neisseria ', 'Neisseria_')  # this is added because rflp profiles are malformatted
                try:
                    fieldvalue = " ".join(line.split()).split(' ')[indexdict[field]]
                    seqdef_profilefields_psql_table.insert_profile_field((schemedict[scheme]['schemename_bigsdb'], field, profile, fieldvalue.replace('_', ' ')))
                except Exception:
                    profiles_to_be_removed.add(profile)
        # third table (profile members):
        # Loci are saved from dir to be able to know which columns to search for in profiles.tsv
        loci: List[str] = next(os.walk(schemedict[scheme]['dirdb']))[1]
        with TblProfileMembers(species) as seqdef_profilemembers_psql_tbl, TblSequences(species) as seqdef_sequences_psql_tbl:
            for locus in loci:
                if not locus.startswith('.'):  # to exclude hidden folders like .git
                    if locus == "'rplF":
                        locus = 'rplF'
                    line: str = profile_line_dict[profile]
                    locusvalue: str = " ".join(line.split()).split(' ')[indexdict[locus]]
                    if locusvalue == '0':  # this will create a ForeignKeyViolation error so we prevent this by inserting a null allele if not yet present
                        nullpresent: List[Tuple[int]] = seqdef_sequences_psql_tbl.count_sequence_null((locus,))
                        if nullpresent[0][0] == 0:
                            seqdef_sequences_psql_tbl.insert_sequence((locus, '0', 'null allele'))
                    try:
                        seqdef_profilemembers_psql_tbl.insert_profile_member((schemedict[scheme]['schemename_bigsdb'], locus, profile, locusvalue))
                    except Exception as exceptionmessage:
                        send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                                   f"profile with field {schemedict[scheme]['scheme_fields'][0]} and value {profile} already exists as another field, find the profile that was misinserted (not all loci have allele_id), "
                                   f"remove it, and all above and restart this script (on db {seqdef_profiles_psql_tbl.name()} on host {socket.gethostname()})")
                        raise Exception(f"profile with field {schemedict[scheme]['scheme_fields'][0]} and value {profile} already exists as another field, find the profile that was misinserted (not all loci have allele_id), "
                                        f"remove it, and all above and restart this script (on db {seqdef_profiles_psql_tbl.name()} on host {socket.gethostname()})")
        # remove profiles with incomplete profile fields
        for profile_to_be_removed in profiles_to_be_removed:
            seqdef_profiles_psql_tbl.delete_profile((schemedict[scheme]['schemename_bigsdb'], profile_to_be_removed))


def _insert_all_profiles() -> None:
    """
    Main function to insert all profiles for the given species
    :return: None
    """
    for species in set(args.species):
        with TblProfiles(species) as seqdef_profiles_psql_tbl:
            schemedict: Dict[str, Dict[str, str]] = bigsdb_config_data['species'][species]['typing_schemes']
            for scheme in schemedict:
                if schemedict[scheme].get('scheme_fields'):
                    with Path('/'.join([schemedict[scheme]['dirdb'], PROFILE_FILE])).open('r') as handle:
                        profiles = handle.readlines()
                    # multiple whitespaces need to be replaced by single whitespace
                    header = " ".join(profiles[0].split()).split(' ')
                    indexdict: Dict[str, int] = {}
                    for index, item in enumerate(header):
                        if item == "'rplF":
                            item = 'rplF'
                        indexdict[item] = index
                    profile_line_dict: Dict[str, str] = {}
                    for line in profiles[1:]:
                        profile_line_dict[" ".join(line.split()).split(' ')[0]] = line

                    listoftuples: List[Tuple[int]] = \
                        seqdef_profiles_psql_tbl.select_profile((schemedict[scheme]['schemename_bigsdb'],))
                    primary_fields = [int(x[0]) for x in listoftuples] if listoftuples is not None else None
                    list_to_be_inserted = set()
                    if primary_fields is None:
                        # table is empty, so all need to be inserted
                        for line in profiles[1:]:
                            list_to_be_inserted.add(" ".join(line.split()).split(' ')[0])
                        __insert_profiles(scheme, schemedict, indexdict, profile_line_dict, list_to_be_inserted, seqdef_profiles_psql_tbl, species)
                    else:
                        # table needs to be updated
                        for line in profiles[1:]:
                            if int(" ".join(line.split()).split(' ')[0]) not in primary_fields:
                                list_to_be_inserted.add(" ".join(line.split()).split(' ')[0])
                            else:
                                continue
                        if list_to_be_inserted:
                            __insert_profiles(scheme, schemedict, indexdict, profile_line_dict, list_to_be_inserted, seqdef_profiles_psql_tbl, species)


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    try:
        _insert_all_profiles()
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")
