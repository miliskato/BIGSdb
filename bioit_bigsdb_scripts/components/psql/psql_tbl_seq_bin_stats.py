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
