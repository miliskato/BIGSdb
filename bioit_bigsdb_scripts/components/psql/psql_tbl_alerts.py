from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblAlerts(DatabaseConnection):
    """
    alerts table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_alert(self, param: Tuple[str, str]) -> None:
        """
        Inserts a new alert for a given type (warning or alert) and a given method (distance_matrix or complete_linkage) # todo method names
        :param param: type (warning or alert), method (distance_matrix or complete_linkage)
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_AL_VAR_TYPE_METH, param)
