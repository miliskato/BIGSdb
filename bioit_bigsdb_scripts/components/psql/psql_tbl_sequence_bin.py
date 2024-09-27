from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblSequenceBin(DatabaseConnection):
    """
    sequence_bin in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def count_sequencebin(self, param: Tuple[str]) -> List[Tuple[int]]:
        """
        Counts the nr of sequences in the sequencebin for the latest version of an isolate
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_SEQBIN_VAR_ISO, param)

    def delete_sequencebin(self,param: Tuple[str]) -> None:
        """
        Delete sequence/contig from the isolates db for a given isolate
        :param param: isolate id
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_SEQBIN_VAR_ISO, param)

    def insert_sequencebin(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts sequence/contig in the database for a given isolate
        :param param: isolate id, sequence, original_designation
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_SEQBIN_VAR_ISO_SEQ_NAME, param)

    def revert_sequencebin_newversion(self, param: List[str]) -> None:
        """
        Reverts the update of the sequences of the latest - 1 version to belong to the latest version
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_REVERSE_TB_SEQBIN_VAR_ISO_ISO, param * 2)
