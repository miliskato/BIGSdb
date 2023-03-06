from typing import Any, List, Optional, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblSequences(DatabaseConnection):
    """
    sequences table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

    def count_sequence_null(self, param: Tuple[str]) -> List[Tuple[int]]:
        """
        Counts the nr of null allele sequences for a given locus (0 or 1)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS, param)

    def count_sequence_allele(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        """
        Counts the nr of allele sequences for a given locus and allele (0 or 1)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS_ALLELE, param)

    def insert_sequence(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts a sequence for a given allele and locus
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_SEQ_VAR_LOCUS_ALLELE_SEQ, param)

    def select_allele_from_locus(self, param: Tuple[str]) -> List[Optional[Tuple[Any]]]:
        """
        Selects all alleles for a given locus
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples of single ints or strings
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS, param)

    def select_sequence_from_locus(self, param: Tuple[str]) -> List[Optional[Tuple[Any]]]:
        """
        Selects the sorted highest sequence for a given locus (used for dummy sequences)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuple of single string
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_SEQUENCE_TB_SEQ_VAR_LOCUS, param)

    def select_allele_from_sequence(self, param: Tuple[str, str]) -> List[Optional[Tuple[Any]]]:
        """
        Selects the allele id for a given locus and sequence
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuple of single int or string
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS_SEQ, param)

    def update_alleleid(self, param: Tuple[str, str, str]) -> None:
        """
        Updates the allele id for a given locus and allele id
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        return self.execute_query(PsqlQueries.SEQ_UPD_ALLELE_TB_SEQ_VAR_LOCUS_ALLELE, param)
