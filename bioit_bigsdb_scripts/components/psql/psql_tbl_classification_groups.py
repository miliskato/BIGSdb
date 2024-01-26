from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblClassificationGroups(DatabaseConnection):
    """
    classification_groupstable in the seqdef database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def count_group(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        """
        Counts the nr of times a group_id occurs in a specific scheme with a specific group_id (0 or 1)
        :param param: cluster group scheme id, group id
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.SEQ_SEL_COUNT_TB_CLGR_VAR_CGSCHID_GRID, param)

    def inactivate_group(self, param: Tuple[str, str]) -> None:
        """
        Updates a specific group to not be active anymore
        :param param: cluster group scheme id, group id
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_UPD_ACTIVE_TB_CLGR_VAR_CGSCHID_GRID, param)

    def insert_group(self, param: Tuple[str, str]) -> None:
        """
        Inserts a new group in a specific clustering group scheme
        :param param: cluster group scheme id, group id
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLGR_VAR_CGSCHID_GRID, param)

    def delete_groups(self, param: Tuple[int]) -> None:
        """
        Inserts a new group in a specific clustering group scheme
        :param param: cluster group scheme id
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_DEL__TB_CLGR_VAR_CGSCHID, param)
