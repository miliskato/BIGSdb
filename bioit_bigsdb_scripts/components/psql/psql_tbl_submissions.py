from typing import Any, List, Optional, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries
import psycopg2

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

    def select_closed_submission(self, param: Tuple[int]) -> List[Optional[Tuple[Union[int, str]]]]:
        """
        Selects all necessary values for closed submissions
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples of ints and strings
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ID_VALUE_OUTCOME_EMAIL_TYPE_TB_SUB_VAR_SUBID, param)

    def update_submission(self, param: Tuple[int, str]) -> None:
        """
        Updates the submission status for a given submission
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_STATUS_TB_SUB_VAR_ID, param)

    def get_submission_id_from_bigs_upload(self):
        """
        Return isolates id for which lab data was submitted through bigsDB interface
        :param param:
        :return: List of isolates id for which lab metadata should be update
        """
        #cursor = psycopg2.connection.cursor()
        #cursor.execute(self.execute_query(PsqlQueries.ISO_SEL_ID_SUBMISSION_THROUGH_BIGS, param))
        #records = cursor.fetchall()
        #return records
        return self.execute(PsqlQueries.ISO_SEL_ID_SUBMISSION_THROUGH_BIGS)