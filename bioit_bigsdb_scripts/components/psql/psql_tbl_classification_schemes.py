from typing import Any, List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblClassificationSchemes(DatabaseConnection):
    """
    classification_schemes table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        super().__init__(species, db_type)
        if self._db_type != 'seqdef' and self._db_type != 'isolates':
            raise ValueError('no such database type')

    def insert_cgscheme_isolates(self, param: Tuple[str, str, str, str, str, str, str]) -> None:
        """
        Inserts a new group in a specific clustering group scheme in the isolates db
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        if self._db_type != 'isolates':
            raise ValueError(f'Wrong db_type {self._db_type} for the current table object/instance')
        self.execute_query(PsqlQueries.ISO_INS__TB_CLSCH_VAR_CGSCHID_SCHEME_NAME_DESC_INCTHR_CGSCHID_CGSCHID, param)

    def insert_cgscheme_seqdef(self, param: Tuple[str, str, str, str, str, str]) -> None:
        """
        Inserts a new group in a specific clustering group scheme in the seqdef db
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type} for the current table object/instance')
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLSCH_VAR_CGSCHID_SCHEME_NAME_DESC_INCTHR_CGSCHID, param)

    def select_cgschemes(self) -> Union[None, List[Tuple[str, str]]]:
        """
        Selects all scheme id and their inclusion tresholds
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None or a list of tuples of two strings (clustering scheme id and inclusion threshold)
        """
        return self.execute(PsqlQueries.SEQ_SEL_CGSCHID_INCTHR_TB_CLSCH_VAR_)
