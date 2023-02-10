from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblSubmissions(DatabaseConnection):
    """
    submissions table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_submission(self, param: Tuple[str]) -> None:
        """
        Inserts a new submission for a given validation type (badqc or resequencing)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_SUB_VAR_VALTYPE, param)

    def select_closed_submissions(self) -> List[Tuple[Union[int, str]]]:
        """
        Selects all necessary values for closed submissions
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples of ints and strings
        """
        return self.execute(PsqlQueries.ISO_SEL_ID_VALUE_OUTCOME_EMAIL_TYPE_TB_SUB_VAR_)

    def update_submission(self, param: Tuple[str]) -> None:
        """
        Updates the submission status for a given submission
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_STATUS_TB_SUB_VAR_ID, param)
