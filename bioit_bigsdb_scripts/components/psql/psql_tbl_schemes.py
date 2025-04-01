from typing import List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblSchemes(DatabaseConnection):
    """
    scheme_members table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        super().__init__(species, db_type)

    def select_scheme_id_cgmlst(self) -> List[Optional[Tuple[int]]]:
        """
        Selects the scheme id of the cgMLST schema in bigsdb (usually 2, after 1 mlst,
        but in the case of stec that has 2 mlst it is 3)
        :return: List of tuples of single strings
        """
        return self.execute(PsqlQueries.UNI_SEL_ID_TB_SCHEME_VAR_)

    def select_scheme_id_based_on_scheme_name(self, param: Tuple[str]) -> List[Optional[Tuple[int]]]:
        """
        Selects the scheme id from bigsdb
        :param param: scheme name
        :return: List with 1 optional tuple containing the scheme id as an integer
        """
        return self.execute_query(PsqlQueries.UNI_SEL_ID_TB_SCHEME_VAR_NAME, param)
