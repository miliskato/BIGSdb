from typing import Any, List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblProjectMembers(DatabaseConnection):
    """
    isolates table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def add_newversion_projectmembers(self, param: List[str]) -> None:
        """
        Adds the new version of an isolate to the same projects that the original version was in
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_PROJMEM_VAR_ISO_ISO, param * 2)