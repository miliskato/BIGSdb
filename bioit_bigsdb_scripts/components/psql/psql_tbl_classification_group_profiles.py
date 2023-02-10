from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblClassificationGroupProfiles(DatabaseConnection):
    """
    classification_group_profiles table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_profile(self, param: Tuple[str, str, str, str]) -> None:
        """
        Inserts a new clustering profile_id and assigns it to a group
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLGRPR_VAR_CGSCHID_GRID_PRID_SCHEME, param)

    def select_profile_group(self, param: Tuple[str, str]) -> Union[None, List[Tuple[int]]]:
        """
        Selects the group id for a specific profile id
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: integer (1-inf) enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_GRID_TB_CLGRPR_VAR_CGSCHID_PRID, param)

    def update_profile_group(self, param: Tuple[str, str, str]) -> None:
        """
        Updates a clustering profile_id's group (needs to be paired with the update in classification group
        profile history)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_UPD_GRID_TB_CLGRPR_VAR_CGSCHID_PRID, param)
