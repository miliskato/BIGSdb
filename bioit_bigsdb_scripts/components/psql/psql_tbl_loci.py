from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblLoci(DatabaseConnection):
    """
    loci table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        if self._db_type != 'seqdef' and self._db_type != 'isolates':
            raise ValueError('no such database type')
        super().__init__(species, db_type)

    def count_locus(self, param: Tuple[str]) -> List[Tuple[int]]:
        """
        Counts the nr of loci where locus = locus (0 or 1)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.UNI_SEL_COUNT_TB_LOCI_VAR_LOCUS, param)

    def insert_locus_isolates(self, param: Tuple[str, str, str, str]) -> None:
        """
        Inserts a locus in the isolates database
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        if self._db_type != 'isolates':
            raise ValueError(f'Wrong db_type {self._db_type} for the current table object/instance')
        self.execute_query(PsqlQueries.ISO_INS__TB_LOCI_VAR_LOCUS_DBNAME_DBID_URL, param)

    def insert_locus_seqdef(self, param: Tuple[str]) -> None:
        """
        Inserts a locus in the sequence definition database
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type} for the current table object/instance')
        self.execute_query(PsqlQueries.SEQ_INS__TB_LOCI_VAR_LOCUS, param)
