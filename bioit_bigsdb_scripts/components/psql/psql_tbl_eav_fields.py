from typing import List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblEavFields(DatabaseConnection):
    """
    eav_fields table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def select_fields_like(self, param: Tuple[str]) -> List[Optional[Tuple[str]]]:
        """
        Selects all the fields where field is like input value (containing % sign)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples containing one string
        """
        return self.execute_query(PsqlQueries.ISO_SEL_FIELD_TB_EAVF_VAR_FIELD, param)

    def select_fields_cgmlstdifferences(self) -> List[Optional[Tuple[str]]]:
        """
        Selects all the fields concerning cgmlst differences
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples containing one string
        """
        return self.select_fields_like(('cgMLST_differences_%',))
