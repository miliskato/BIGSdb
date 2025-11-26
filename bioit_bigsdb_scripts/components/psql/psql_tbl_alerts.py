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
        :return: None
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_alert(self, param: Tuple[str, str]) -> None:
        """
        Inserts a new alert for a given type (warning or alert) and a given method (distance matrix or single linkage)
        :param param: type (warning or alert), method (distance matrix or single linkage)
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_AL_VAR_TYPE_METH, param)

    def update_warning_to_alert_and_status_to_pending(self, param: Tuple[str]) -> None:
        """
        Updates a given alert's type to 'alert', and its status to 'pending', whatever it was before
        :param param: alert_id as str
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_TYPE_STATUS_TB_ALDE_VAR_ALID, param)

    def update_status_to_pending(self, param: tuple[str]) -> None:
        """
        Updates a given alert's status to 'pending'.
        :param param: alert_id as str
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_STATUS_TB_ALDE_VAR_ALID, param)

    def delete_alert(self, param: tuple[str]) -> None:
        """
        Deletes an alert based on the isolate id in the alerts details table.
        :param param: Isolate id as str
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_AL_VAR_ID, param)
