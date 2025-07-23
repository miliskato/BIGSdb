from typing import List, Optional, Tuple, Union, Literal

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries
from ...utils.literal_helper import validate_literal

QualityLiteral = Literal['warning', 'good']
QualityValues = Union[QualityLiteral, str]

ResequencingLiteral = Literal['yes', 'no']
ResequencingValues = Union[ResequencingLiteral, str]

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

    def insert_submission(self, param: Tuple[QualityValues, ResequencingValues]) -> None:
        """
        Inserts a new submission for a given quality (good or warning) and if it is a resequencing or not.
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        validate_literal(param[0], QualityLiteral)
        validate_literal(param[1], ResequencingLiteral)
        self.execute_query(PsqlQueries.ISO_INS__TB_SUB_VAR_QUAL_RESEQ, param)

    def select_closed_submission(self, param: Tuple[str]) -> List[Optional[Tuple[Union[int, str]]]]:
        """
        Selects all necessary values for closed submissions
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples of ints and strings
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ID_VALUE_OUTCOME_EMAIL_TYPE_TB_SUB_VAR_SUBID, param)

    def update_submission(self, param: Tuple[str]) -> None:
        """
        Updates the submission status for a given submission
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_STATUS_TB_SUB_VAR_ID, param)

    def get_submission_id_from_bigs_upload(self) -> List[Tuple[str]]:
        """
        Select submission ids submitted through bigsDB interface with status closed
        :return: List of corresponding submissions ids
        """
        return self.execute(PsqlQueries.ISO_SEL_ID_TB_SUB_VAR_STATUS)

    def get_submission_ids_for_validated_warningqcs(self) -> List[Tuple[str]]:
        """
        Select submission ids for warningqc where status is closed and outcome is good
        :return: List of corresponding submissions ids
        """
        return self.execute(PsqlQueries.ISO_SEL_SUBID_TB_SUB_VAR_)

    def get_submission_ids_for_specific_status_and_quality(self, param: Tuple[str, str]) -> List[Tuple[str]]:
        """
        Select submission ids from rows where status and quality correspond to params provided to the method
        :param param: status and quality values
        :return: List of corresponding submissions ids
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ID_TB_SUB_VAR_STATUS_QUALITY, param)

    def validate_pending_warningqcs(self):
        """
        This function will set outcome of all submitted warningqcs to "good" and turn status from "pending" to "closed"
        :return: None
        """
        return self.execute(PsqlQueries.ISO_UPD_STATUS_OUTCOME_TB_SUB_VAR_)

    def validate_submission(self, param: Tuple[str]) -> None:
        """
        This function will set outcome of all submitted warningqcs to "good" and turn status from "pending" to "closed"
        :param param: submission id for which we want to validate the submission
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_STATUS_OUTCOME_TB_SUB_VAR_SUBID, param)
