from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblClassificationGroupProfileHistory(DatabaseConnection):
    """
    classification_group_profiles_history table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_history(self, param: Tuple[str, str, str, str]) -> None:
        """
        Inserts a clustering profiles profile_id previous group into a history table after the profile's
        group has been modified in the classification group profiles table
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLGRPRHIST_VAR_SCHEME_PRID_CGSCHID_PREVGR, param)
