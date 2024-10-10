from typing import List, Optional, Tuple

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
        :return: None
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_alert_metadata(self, param: Tuple[str, str]) -> None:
        """
        Inserts an alert metadata value for a given alert metadata field for the last inserted validation.
        :param param: alert detail field, value
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ALDE_VAR_FIELD_VALUE, param)

    def select_alert_for_isolate(self, param: Tuple[str, str]) -> Optional[List[Tuple[int, str]]]:
        """
        Selects the alert id and the alert type (warning/alert) based on the isolate name and computation method.
        :param param: isolate bigsdb id as str, alert computation method (single linkage/distance matrix)
        :return: None or list of tuple of alert info: (alert_id, type)
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ALID_TYPE_TB_ALDE_VAR_ISOLATE_METH, param)

    def update_details_for_alert_id(self, param: Tuple[str, str, str]) -> None:
        """
        Updates the alert details value for a given field and a given alert id.
        :param param: value, field, alert_id as str
        :return: None
        """
        return self.execute_query(PsqlQueries.ISO_UPD_VAL_TB_ALDE_VAR_ALID_FIELD, param)
