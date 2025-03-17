from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblFailedIsolates(DatabaseConnection):
    """
    failed_isolates table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_failure(self, param: Tuple[str, str]) -> None:
        """
        insert pseudo_id to keep track of isolates that were no properly inserted from mongo.
        :param param: pseudo id of the isolates
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_FAIL_ISO_VAR_ID_MESS, param)
