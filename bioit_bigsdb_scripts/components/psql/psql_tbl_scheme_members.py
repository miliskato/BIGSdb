from typing import Any, List, Optional, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblSchemeMembers(DatabaseConnection):
    """
    scheme_members table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        super().__init__(species, db_type)

    def check_scheme_member_presence(self, param: Tuple[int]) -> List[Tuple[bool]]:
        """
        Check if scheme members exist for this given scheme id
        :param param: scheme id from BIGSdb
        :return: t or f
        """
        return self.execute(PsqlQueries.UNI_SEL_EXISTS_TB_SCHMEM_VAR_SCHID, param)

    def count_scheme_member(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        """
        Counts the nr of times a locus is a a scheme_member for a given locus and scheme (0 or 1)
        :param param: scheme name, locus name
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.UNI_SEL_COUNT_TB_SCHMEM_VAR_SCHEME_LOCUS, param)

    def insert_scheme_member(self, param: Tuple[str, str]) -> None:
        """
        Inserts a locus as a scheme_member for a given scheme
        :param param: scheme name, locus name
        :return: None
        """
        self.execute_query(PsqlQueries.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS, param)

    def select_loci_amr(self) -> List[Optional[Tuple[str]]]:
        """
        Selects all loci that are scheme_members of the mycobacterium amr_who scheme
        :return: List of tuples of single strings
        """
        return self.execute(PsqlQueries.UNI_SEL_LOCUS_TB_SCHMEM_VAR_)
