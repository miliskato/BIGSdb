from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblFailedInsertions(DatabaseConnection):
    """
    failed_insertions table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_message_id(self, param: Tuple[str, str]) -> None:
        """
        inserts a row to keep track of the new message
        :param param: message id, pseudo id
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_FAILINS_VAR_MSGID_PSEUDOID, param)

    def update_exception_for_message_id(self, param: Tuple[str, str]) -> None:
        """
        specifies type of exception for this message_id
        :param param: type of exception, message id
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_COM_TB_FAILINS_VAR_MSGID, param)

    def delete_message_id(self, param: Tuple[str]) -> None:
        """
        deletes entry for this message id
        :param param: message id
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_FAILINS_VAR_MSGID, param)
