from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblClientDbaseLoci(DatabaseConnection):
    """
    client_dbase_loci table in the seqdef database (required for rest api)
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_locus(self, param: Tuple[str, str, str, str]) -> None:
        """
        Inserts a locus into the client dbase loci, necessary for rest api broadcasting
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLDBLOCI_VAR_LOCUS, param)
