from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblTempIsolatesSchemeFields(DatabaseConnection):
    """
    temp_isolates_scheme_fields_ table like in the isolates database
    """

    def __init__(self, species: str, scheme_id: int) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param scheme_id: BIGSdb internal id for the target scheme (NB: often 2 for cgMLST except in STEC)
        """
        self._db_type = 'isolates'
        self._scheme_id = scheme_id
        super().__init__(species, self._db_type)

    def delete_profile(self, param: Tuple[str]) -> None:
        """
        Delete rows in temp_isolates_scheme_fields_ corresponding to isolate passed in param
        :param param: variable to feed to the PSQL query: isolate name
        :return: None
        """
        param_with_target_scheme=[self._scheme_id, param[0]]
        self.execute_query_client_cursor(PsqlQueries.ISO_DEL__TB_TPISOSCHFIELD_VAR_SCHID_ISO, param_with_target_scheme)
