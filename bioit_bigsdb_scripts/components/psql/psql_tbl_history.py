from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblHistory(DatabaseConnection):
    """
    history table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_history_id(self, param: Tuple[str, str]) -> None:
        """
        Inserts a history message for a given isolate id
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_HIST_VAR_ID_MESS, param)

    def insert_history_isolate(self, param: Tuple[str, str]) -> None:
        """
        Inserts a history message for a given isolatename
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_HIST_VAR_ISO_MESS, param)
