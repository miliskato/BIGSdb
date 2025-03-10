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

    def insert_fields_16s(self, param: Tuple[str]) -> None:
        """
        Inserts a metadata field in the NCBI 16S category
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVF_VAR_FIELD, param)

    def insert_text_field(self, param: Tuple[str, str]) -> None:
        """
        Inserts a metadata field in the NCBI 16S category
        :param param: field to insert, its category
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVF_VAR_FIELD_TEXT, param)

    def select_fields_amr(self) -> List[Optional[Tuple[str]]]:
        """
        Selects all the fields in the mycobacterium-specific amr who category
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

    def select_fields_of_a_category(self, param: Tuple[str]) -> List[Optional[Tuple[str]]]:
        """
        Selects all the fields where category is equal to the input value
        :param param: variables to feed to the PSQL query in that case 'category' on which we want to filter the table
        :return: list of tuples containing one string
        """
        return self.execute_query(PsqlQueries.ISO_SEL_FIELD_TB_EAVF_VAR_CAT, param)

    def select_fields_cgmlstdifferences(self) -> List[Optional[Tuple[str]]]:
        """
        Selects all the fields concerning cgmlst differences
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples containing one string
        """
        return self.select_fields_like(('cgMLST_differences_%',))

    def exists_in_eav_field(self, param: Tuple[str, str]) -> bool:
        """
        Return the description stored for the given field
        :param param: field from eav_fields table, category for this field
        :return: True if present, False if not
        """
        count_occurence = self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_EAVF_VAR_FIELD_VAR_CAT, param)
        return True if count_occurence[0][0] > 0 else False
