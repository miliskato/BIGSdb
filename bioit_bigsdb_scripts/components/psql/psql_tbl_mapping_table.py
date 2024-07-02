from typing import Any, List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblMappingTable(DatabaseConnection):
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

    def select_pseudoid_for_isolate(self, param: Tuple[str]) -> List[Tuple[Optional[str]]]:
        """
        Selects the pseudo_id of an isolate.
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: pseudo id as str
        """
        return self.execute_query(PsqlQueries.ISO_SEL_PSEUDOID_TB_MT_VAR_ISO, param)
