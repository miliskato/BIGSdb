from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblEavBoolean(DatabaseConnection):
    """
    eav_boolean table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_eav_isolate(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts a boolean metadata value for a specific isolate and a specific metadata field
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVB_VAR_ISO_FIELD_VAL, param)

    def insert_eav_id(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts a boolean metadata value for a specific isolate and a specific metadata field
        :param param: variables to feed to the PSQL query: isolate id, field, value
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVB_VAR_ID_FIELD_VAL, param)

    def delete_eavbool_for_isolate(self, param: Tuple[str]) -> None:
        """
        Delete all boolean metadata value for a specific isolate
        :param param: isolate name
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_EAVB_VAR_ISO, param)
