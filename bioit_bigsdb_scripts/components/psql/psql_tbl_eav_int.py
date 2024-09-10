from typing import Any, List, Optional, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblEavInt(DatabaseConnection):
    """
    eav_int table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_eav_int_isolate(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts a metadata field in the NCBI 16S category
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query - isolate_id, field, value
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVI_VAR_ISO_FIELD_VAL, param)