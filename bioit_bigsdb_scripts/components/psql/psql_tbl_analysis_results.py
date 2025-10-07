from typing import Tuple

from psycopg.types.json import Json, Jsonb

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblAnalysisResults(DatabaseConnection):
    """
    Analysis results table in the isolates database.
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_analysis_results_isolate_name(self, param: Tuple[str, str, Json | Jsonb]) -> None:
        """
        Add the analysis results of a specific assay for a specific isolate ID.
        :param param: name of the assay, the isolate original id (SXXBDXXXXXX) and the results as Jsonb
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ANA_RES_VAR_NAM_ISO_RES, param)

    def insert_analysis_results_isolate_id(self, param: Tuple[str, str, Json | Jsonb]) -> None:
        """
        Add the analysis results of a specific assay for a specific isolate ID.
        :param param: name of the assay, the id of the isolate and the results as Jsonb
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ANA_RES_VAR_NAM_ISO_ID_RES, param)

    def delete_analysis_results_isolate_name(self, param: Tuple[str]) -> None:
        """
        Delete the analysis results for a certain isolate.
        :param param: isolate original id from bigsdb (SXXBDXXXXXX)
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_ANA_RES_VAR_ISO, param)

    def is_analysis_results_already_present(self, param: Tuple[str, str]) -> list[Tuple[bool]]:
        """
        Check if analysis results for a specific assay and for a specific isolate ID is already present in the table.
        :param param: the name of the assay and the isolate id
        :return: True if results are already present, False otherwise
        """
        return self.execute_query(PsqlQueries.ISO_SEL_EXISTS_TB_ANA_RES_VAR_NAME_ISO, param)

    def update_analysis_results_isolate_id(self, param: Tuple[Jsonb, str, str]) -> None:
        """
        Update analysis results for a specific assay and for a specific isolate ID.
        :param param: new results as Jsonb, the isolate id and the name of the assay
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPDATE_TB_ANA_RES_VAR_RES_NAME_ISO_ID, param)
