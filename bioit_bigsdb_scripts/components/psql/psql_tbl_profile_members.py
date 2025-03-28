from typing import Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblProfileMembers(DatabaseConnection):
    """
    profile_members table in the seqdef database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'seqdef'
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

    def insert_profile_member(self, param: Tuple[str, str, str, str]) -> None:
        """
        Inserts a profile member; a value for a given locus for a given profile
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROFMEM_VAR_SCHEME_SCHFIELD_PROFID_VALUE, param)

    def insert_all_loci_of_profile(self, data) -> None:
        """
        Inserts all loci of the prodile in profile_members table
        :param data: data to insert into the table (consisting of values used to fill in each row associated to this profile).
        :return: None
        """
        cur = self.cursor
        args_str = ','.join(cur.mogrify('(%s, %s, %s, %s, %s, %s)', row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} VALUES".format(table='profile_members') + args_str)
