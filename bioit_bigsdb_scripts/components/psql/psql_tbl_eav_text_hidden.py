from typing import Any, List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblEavTextHidden(DatabaseConnection):
    """
    eav_text_hidden table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        This is a custom table by bioit that was not previously present in Bigsdb.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_hidden_isolate(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts hidden metadata value where isolatename is certain value and metadata field is certain value
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVTH_VAR_ISO_FIELD_VAL, param)

    def select_hidden(self, param: Tuple[str]) -> List[Optional[Tuple[Any]]]:
        """
        Selects all values for all isolates where field is a certain value
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: list of tuples of any values
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ID_VAL_ISO_TB_EAVTH_VAR_FIELD, param)

    def select_mongo_resultsversion(self, param: Tuple[str]) -> List[Optional[Tuple[int]]]:
        """
        Selects corresponding results version mongodb for a given isolate
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None or integer value enclosed by a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_VERSION_TB_EAVTH_VAR_ISO, param)
