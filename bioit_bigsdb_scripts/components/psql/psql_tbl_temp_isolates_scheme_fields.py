from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblTempIsolatesSchemeFields(DatabaseConnection):
    """
    temp_isolates_scheme_fields_ table like in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def delete_profile(self, param: Tuple[int, str]) -> None:
        """
        Delete rows in temp_isolates_scheme_fields corresponding to isolate passed in param
        :param param: variables to feed to the PSQL query, bigsdb scheme id and isolate name
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_TPISOSCHFIELD_VAR_ISO, param)
