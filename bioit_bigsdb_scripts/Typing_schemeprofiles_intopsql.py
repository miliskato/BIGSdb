import argparse
import logging
import os
import socket
import sys
import traceback
from datetime import date

import pandas as pd
from pathlib import Path
from typing import Dict, Final, List, Tuple

from psycopg2._psycopg import cursor

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblProfiles, TblProfileFields, TblProfileMembers, TblSchemes, \
    TblSequences
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


class TypingSchemeProfilesIntoPsql:
    """
    Class containing function to insert typing scheme profiles.
    """

    def __init__(self, species_list: List[str], dont_send_email: bool = False) -> None:
        """
        Initialises this class and executes the main function: _insert_alleles
        :param species_list: list of commonly used bioit species name: either genus or specific like stec.
        :param dont_send_email: do not send emails, only log
        :return: None
        """
        self._species_list = species_list
        self._dont_send_email = dont_send_email
        self._bigsdb_config_data = get_bigsdb_config_data()

        try:
            self._insert_all_profiles()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}", dont_send_email=self._dont_send_email)
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

    @staticmethod
    def __insert_profiles(scheme: str, schemedict: Dict[str, Dict[str, str]], profile_df: pd.DataFrame,
                          set_to_be_inserted: set[str], seqdef_profiles_psql_tbl: TblProfiles, species: str) -> None:
        """
        Inserts profiles for a given scheme in a given species database (seqdef_profiles_psql_table)
        :param scheme: the currently iterating scheme
        :param profile_df: pandas dataframe containing profiles from tsv files
        :param profile_line_dict: dictionary of main numeric profile fields (often ST) and their corresponding lines in the tsv
        :param set_to_be_inserted: list of main numeric profile fields (often ST) to be inserted
        :param seqdef_profiles_psql_tbl: seqdef profiles table/ connection instance for a given species
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: None
        """
        # since we only need one db per scheme, it can stay open during the entire definition

        dict_replacement = {'?':'','Neisseria ':'Neisseria_','N':'0'}
        profile_df = profile_df.replace(dict_replacement)
        first_col_name = profile_df.columns.values[0]
        loci: List[str] = next(os.walk(schemedict[scheme]['dirdb']))[1]
        loci_only = [x for x in loci if not x.startswith('.')] # to exclude hidden folders like .git
        bigsdb_scheme_name = schemedict[scheme]['schemename_bigsdb']
        with TblSchemes(species,'seqdef') as tbl_schemes:
            scheme_id_psql = tbl_schemes.select_scheme_id_based_on_scheme_name((bigsdb_scheme_name,))[0][0]
        for profile_id in set_to_be_inserted:

            profile_line_df = profile_df[profile_df[first_col_name]==profile_id]
            # first table (profiles):
            seqdef_profiles_psql_tbl.insert_profile((bigsdb_scheme_name, profile_id))
            profiles_to_be_removed = set()
            # second table (profile fields):
            with TblProfileFields(species) as seqdef_profilefields_psql_table:
                for field in schemedict[scheme]['scheme_fields']:
                    try:
                        field_value = profile_line_df[field].values[0]
                        seqdef_profilefields_psql_table.insert_profile_field(
                            (bigsdb_scheme_name, field, profile_id, field_value.replace('_', ' ')))
                    except Exception:
                        profiles_to_be_removed.add(profile_id)
            # third table (profile members):
            # Loci are saved from dir to be able to know which columns to search for in profiles.tsv
            with TblProfileMembers(species) as seqdef_profilemembers_psql_tbl, TblSequences(
                    species) as seqdef_sequences_psql_tbl:
                table_profile = []
                for locus in loci_only:
                    if locus == 'rplF':
                        profile_line_df = profile_line_df.rename(columns={"'rplF": "rplF"})
                    locus_value = TypingSchemeProfilesIntoPsql.___return_locus_allele(locus, profile_line_df, scheme)

                    if locus_value == '0':  # this will create a ForeignKeyViolation error so we prevent this by inserting a null allele if not yet present
                        nullpresent: List[Tuple[int]] = seqdef_sequences_psql_tbl.count_sequence_null((locus,))
                        if nullpresent[0][0] == 0:
                            seqdef_sequences_psql_tbl.insert_sequence((locus, '0', 'null allele'))
                    table_profile.append((scheme_id_psql, locus, profile_id, locus_value, 1, str(date.today())))
                try:
                    seqdef_profilemembers_psql_tbl.method_string_building(table_profile)
                except Exception as exceptionmessage:
                    send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                                f"profile with field {schemedict[scheme]['scheme_fields'][0]} and value {profile_id} already exists as another field, find the profile that was misinserted (not all loci have allele_id), "
                                f"remove it, and all above and restart this script (on db seqdef profiles members on host {socket.gethostname()})")
                    raise Exception(
                        f"profile with field {schemedict[scheme]['scheme_fields'][0]} and value {profile_id} already exists as another field, find the profile that was misinserted (not all loci have allele_id), "
                        f"remove it, and all above and restart this script (on db seqdef profiles members on host {socket.gethostname()})")
            # remove profiles with incomplete profile fields
            for profile_to_be_removed in profiles_to_be_removed:
                seqdef_profiles_psql_tbl.delete_profile(
                    (bigsdb_scheme_name, profile_to_be_removed))


    @staticmethod
    def ___return_locus_allele(locus: str, df_row: pd.DataFrame, scheme: str) -> str:
        """
        return locus value (allele) for the given profile
        :param locus: locus id
        :param df_row: pandas df containing only the row for the profile of interest
        :param scheme: scheme name
        :return: locus allelic value
        """
        try:
            locus_value = df_row[locus].values[0]
        except KeyError as keyerror_message:
            send_email(f"key error {keyerror_message} not found on {socket.gethostname()}\n{traceback.format_exc()}",
                       f"locus {keyerror_message} not found in profiles.tsv for scheme {scheme} on host {socket.gethostname()}")
            raise Exception(f"locus {keyerror_message} not found in profiles.tsv for scheme {scheme}")
        return locus_value

    def _insert_all_profiles(self) -> None:
        """
        Main function to insert all profiles for the given species
        :return: None
        """
        for species in set(self._species_list):
            schemedict: Dict[str, Dict[str, str]] = self._bigsdb_config_data['species'][species]['typing_schemes']
            with TblProfiles(species) as seqdef_profiles_psql_tbl:
                for scheme in schemedict:
                    if schemedict[scheme].get('scheme_fields') is None:
                        continue

                    path_to_profiles = '/'.join([schemedict[scheme]['dirdb'], PROFILE_FILE])
                    profiles = self.open_profiles_metadata_file(path_to_profiles, scheme, species)

                    list_of_profile_ids: List[Tuple[int]] = \
                        seqdef_profiles_psql_tbl.select_profile((schemedict[scheme]['schemename_bigsdb'],))

                    primary_fields = [str(x[0]) for x in list_of_profile_ids]
                    profiles = profiles[~profiles[profiles.columns[0]].isin(primary_fields)]
                    if profiles.empty:
                        continue
                    set_to_be_inserted = set(profiles.iloc[:, 0].to_list())

                    if not profiles.empty:
                        self.__insert_profiles(scheme, schemedict, profiles, set_to_be_inserted,
                                               seqdef_profiles_psql_tbl, species)

    @staticmethod
    def open_profiles_metadata_file(file_path: str, scheme: str, species: str) -> pd.DataFrame:
        """
        read profiles metadata file and return them as a pandas.DataFrame
        :param file_path: string = path to the file
        :param scheme: scheme name from bigsdb config file
        :param species: species name
        :return: pandas.DataFrame
        """
        profiles = pd.read_csv(file_path, delimiter='\t', dtype=str)
        if scheme == f"{species}_rmlst":
            mask = profiles['genus'].str.contains(species, na=False, case=False)
            profiles = profiles[mask]
        profiles.rename(columns={"'rplF": "rplF"})

        return profiles


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    TypingSchemeProfilesIntoPsql(args.species)
