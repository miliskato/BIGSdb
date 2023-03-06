from typing import Any, List, Optional, Tuple, Union

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

    def insert_fields_16s(self, param: Tuple[str]) -> None:
        """
        Inserts a metadata field in the NCBI 16S category
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVF_VAR_FIELD, param)

    def select_fields_amr(self) -> List[Optional[Tuple[str]]]:
        """
        Selects all the fields in the mycobacterium-specific amr who category
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples containing one string
        """
        return self.execute(PsqlQueries.ISO_SEL_FIELD_TB_EAVF_VAR_)

    def select_fields_like(self, param: Tuple[str]) -> List[Optional[Tuple[str]]]:
        """
        Selects all the fields where field is like input value (containing % sign)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples containing one string
        """
        return self.execute_query(PsqlQueries.ISO_SEL_FIELD_TB_EAVF_VAR_FIELD, param)

    def select_count_16s(self, param: Tuple[str]) -> List[Tuple[int]]:
        """
        Counts the nr of fields that are equal to a given field (0 or 1)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_EAVF_VAR_FIELD, param)
