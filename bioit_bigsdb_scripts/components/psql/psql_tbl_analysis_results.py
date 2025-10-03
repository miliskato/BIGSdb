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
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ANA_RES_VAR_NAM_ISO_RES, param)

    def delete_analysis_results_isolate_name(self, param: Tuple[str]) -> None:
        """
        Delete the analysis results for a certain isolate.
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_ANA_RES_VAR_ISO, param)
