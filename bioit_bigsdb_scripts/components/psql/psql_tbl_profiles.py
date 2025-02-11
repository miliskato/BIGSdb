from typing import List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblProfiles(DatabaseConnection):
    """
    profiles table in the seqdef database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

    def delete_profile(self, param: Tuple[str, str]) -> None:
        """
        Deletes a profile for a given profile_id
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_DEL__TB_PROF_VAR_SCHEME_PROFID, param)

    def insert_profile(self, param: Tuple[str, str]) -> None:
        """
        Inserts a new profile
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROF_VAR_SCHEME_PROFID, param)

    def select_profile(self, param: Tuple[str]) -> List[Optional[Tuple[int]]]:
        """
        Select all profile_id's for a given scheme
        :param param: name of the scheme in BIGSdb
        :return: all "profile_id" found in the table for this specific scheme
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_PROFID_TB_PROF_VAR_SCHEME, param)
