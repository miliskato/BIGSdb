from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblEavText(DatabaseConnection):
    """
    eav_text table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def delete_eav(self, param: Tuple[str, str]) -> None:
        """
        Delete metadata value from eav text where isolate id is certain value and metadata field is certain value
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_EAVT_VAR_ID_FIELD, param)

    def delete_all_eav_of_isolate(self, param: Tuple[str]) -> None:
        """
        Delete all eav field for a specific isolate id
        :param param: isolate name
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_EAVT_VAR_ISO, param)

    def insert_eav_id(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts metadata value where isolate id is certain value and metadata field is certain value
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVT_VAR_ID_FIELD_VAL, param)

    def insert_eav_isolate(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts metadata value where isolatename is certain value and metadata field is certain value
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVT_VAR_ISO_FIELD_VAL, param)

    def update_eav_id(self, param: Tuple[str, str, str]) -> None:
        """
        Updates metadata value where isolate id is certain value and metadata field is certain value
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_VAL_TB_EAVT_VAR_ID_FIELD, param)

    def select_count_eav_id(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        """
        Counts the nr of fields with a given isolate id and field name
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_EAVT_VAR_ID_FIELD, param)

    def select_count_eav_field(self, param: Tuple[str]) -> List[Tuple[int]]:
        """
        Counts the nr of fields with a field name
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_EAVT_VAR_FIELD, param)