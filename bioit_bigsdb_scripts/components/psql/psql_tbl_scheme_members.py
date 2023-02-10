from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblSchemeMembers(DatabaseConnection):
    """
    scheme_members table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        if self._db_type != 'seqdef' and self._db_type != 'isolates':
            raise ValueError('no such database type')
        super().__init__(species, db_type)

    def count_scheme_member(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        """
        Counts the nr of times a locus is a a scheme_member for a given locus and scheme (0 or 1)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.UNI_SEL_COUNT_TB_SCHMEM_VAR_SCHEME_LOCUS, param)

    def insert_scheme_member(self, param: Tuple[str, str]) -> None:
        """
        Inserts a locus as a scheme_member for a given scheme
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS, param)

    def select_loci_amr(self) -> List[Tuple[str]]:
        """
        Selects all loci that are scheme_members of the mycobacterium amr_who scheme
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: List of tuples of single strings
        """
        return self.execute(PsqlQueries.UNI_SEL_LOCUS_TB_SCHMEM_VAR_)
