from typing import List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblMappingTable(DatabaseConnection):
    """
    mapping table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def select_pseudo_id_for_isolate(self, param: Tuple[str]) -> List[Tuple[Optional[str]]]:
        """
        Selects the pseudo_id of an isolate.
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query, in this case the isolate name.
        :return: pseudo id as str
        """
        return self.execute_query(PsqlQueries.ISO_SEL_PSEUDOID_TB_MT_VAR_ISO, param)

    def select_isolate_id_for_pseudo_id(self, param: Tuple[str]) -> str | None:
        """
        Selects the isolate_id for a given pseudo_id
        :param param: variables to feed to the PSQL query, in this case the pseudo_id.
        :return: isolate_id as str or None if no equivalence in the mapping table
        """
        result = self.execute_query(PsqlQueries.ISO_SEL_ID_TB_MT_VAR_PSEUDOID, param)
        return str(result[0][0]) if len(result) > 0 else None


    def insert_mapping_for_isolate(self, param: Tuple[str, str]) -> None:
        """
        Inserts the isolate name + pseudo_id pair for an isolate.
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query, in this case isolate name + pseudo_id.
        :return: None
        """
        param_arranged_for_psql = (param[0], param[0], param[1])
        return self.execute_query(PsqlQueries.ISO_INS__TB_MT_VAR_ISO_PSEUDOID, param_arranged_for_psql)
