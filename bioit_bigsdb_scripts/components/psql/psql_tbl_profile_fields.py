from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblProfileFields(DatabaseConnection):
    """
    profile_fields table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

    def insert_profile_field(self, param: Tuple[str, str, str, str]) -> None:
        """
        Inserts a profile field value for a given scheme and scheme field
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROFFIELDS_VAR_SCHEME_SCHFIELD_PROFID_VALUE, param)
