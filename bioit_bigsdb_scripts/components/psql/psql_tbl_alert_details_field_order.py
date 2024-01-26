from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblAlertDetailsFieldOrder(DatabaseConnection):
    """
    alert_details_field_order table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_alert_details_indices(self, param: Tuple[str, int]) -> None:
        """
        Inserts indices for given fields that have also been inserted in the alert_details table.
        These indices are a prerequisite for bigsdb but do not serve much purpose.
        :param param: alert detail field, index
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ALDEFO_VAR_FIELD_INDEX, param)
