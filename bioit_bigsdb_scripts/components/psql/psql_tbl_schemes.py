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
        Selects all loci that are scheme_members of the mycobacterium amr_who scheme
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: List of tuples of single strings
        """
        return self.execute(PsqlQueries.UNI_SEL_ID_TB_SCHEME_VAR_)
