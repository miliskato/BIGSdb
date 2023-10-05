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

    def get_field_and_value_from_submission(self, param: Tuple[str]) -> List[Tuple[Any]]:
        """
        Return field and value columns from isolate_submission_isolates filtered by submission_id
        :param param: submission_id
        :return: List of tuples containing the "field" and "value" items
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ALL_TB_ISOSUBISO_VAR_SUBID, param)
