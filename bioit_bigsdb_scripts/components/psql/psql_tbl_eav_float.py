from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblEavFloat(DatabaseConnection):
    """
    eav_float table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: None
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def delete_eav_float_for_isolate(self, param: Tuple[str]) -> None:
        """
        Delete all eav float values for a specific isolate id
        :param param: isolate name
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_EAVFL_VAR_ISO, param)

    def insert_eav_float_isolate(self, param: Tuple[str, str, float]) -> None:
        """
        Inserts a metadata field (currently rMLST taxonomy identification)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query - isolate_id, field, value
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVFL_VAR_ISO_FIELD_VAL, param)
