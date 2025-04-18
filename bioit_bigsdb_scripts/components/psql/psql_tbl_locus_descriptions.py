from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblLocusDescriptions(DatabaseConnection):
    """
    locus_descriptions table in both databases
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def delete_locus_description(self, param: Tuple[str]) -> None:
        """
        Deletes the description for a given locus (used for gene detection cluster loci)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_DEL__TB_LOCDES_VAR_LOCUS, param)

    def insert_locus_description(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts a description for a given locus (used for gene detection cluster loci)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_LOCDES_VAR_LOCUS_PROD_DES, param)
