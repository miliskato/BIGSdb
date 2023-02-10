from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblIsolateSubmissionFieldOrder(DatabaseConnection):
    """
    isolate_submission_field_order table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_validation_indexes(self, param: Tuple[str, int]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_ISOSUBFO_VAR_FIELD_INDEX, param)
