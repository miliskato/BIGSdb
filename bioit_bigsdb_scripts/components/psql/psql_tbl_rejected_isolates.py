from typing import Tuple

from bioit_bigsdb_scripts.components.psql.databaseconnection import DatabaseConnection
from bioit_bigsdb_scripts.components.psql.psql_queries import PsqlQueries


class TblRejectedIsolates(DatabaseConnection):
    """
    Rejected isolates table in the isolates database.
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_isolate(self, param: Tuple[str, str, str, str, str]) -> None:
        """
        Inserts a new rejected isolate.
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query; isolate, insertion_date, rejection_reasons,
        insertion_type, report
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_REJISO_VAR_ISO_DATE_REJREAS_TYPE_REPORT, param)

    def delete_isolate(self, param: Tuple[str]) -> None:
        """
        Deletes a rejected isolate.
        :param param: variable to feed to the PSQL query, which also sanitizes this variable,
        necessary parameter visible in the PSQL query name and query; isolate
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_REJISO_VAR_ISO, param)

    def exists_isolate(self, param: Tuple[str]) -> list[Tuple[bool]]:
        """
        Checks if a certain rejected isolate already exists in the table.
        :param param: variable to feed to the PSQL query, which also sanitizes this variable,
        necessary parameter visible in the PSQL query name and query; isolate
        :return: t or f
        """
        return self.execute_query(PsqlQueries.ISO_SEL_EXISTS_TB_REJISO_VAR_ISO, param)

    def select_last_isolate_id(self) -> int:
        """
        Selects the id of the lastly added isolate.
        :return: id of the lastly added isolate
        """
        isolate_id_tuple = self.execute(PsqlQueries.ISO_SEL_MAX_REJISO)
        return isolate_id_tuple[0][0] if isolate_id_tuple else 0
