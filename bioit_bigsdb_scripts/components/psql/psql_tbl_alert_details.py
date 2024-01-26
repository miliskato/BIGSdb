from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblAlertDetails(DatabaseConnection):
    """
    alert_details table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_alert_metadata(self, param: Tuple[str, str]) -> None:
        """
        Inserts an alert metadata value for a given alert metadata field for the last inserted validation
        :param param: alert detail field, value
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ALDE_VAR_FIELD_VALUE, param)
