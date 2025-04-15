from typing import List

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblSeqBinStats(DatabaseConnection):
    """
    seqbin_stats in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def revert_seqbinstats_newversion(self, param: List[str]) -> None:
        """
        Reverts the update of the seqbinstats of the latest - 1 version to belong to the latest version
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_REVERSE_TB_SEQBINSTATS_VAR_ISO_ISO, param * 2)
