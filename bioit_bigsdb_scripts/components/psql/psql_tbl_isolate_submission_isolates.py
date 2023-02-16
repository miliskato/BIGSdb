from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblIsolateSubmissionIsolates(DatabaseConnection):
    """
    isolate_submission_isolates table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_validation_metadata(self, param: Tuple[str, str]) -> None:
        """
        Inserts a validation metadata value for a given validation metadata field for the last inserted validation
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ISOSUBISO_VAR_FIELD_VALUE, param)
