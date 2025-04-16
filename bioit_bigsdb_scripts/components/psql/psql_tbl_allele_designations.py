from typing import List, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblAlleleDesignations(DatabaseConnection):
    """
    allele_designations table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def count_designations(self, param: Tuple[str, str, str]) -> List[Tuple[int]]:
        """
        Counts the nr of allele designations for a specific sample, locus, and allele (0 or 1)
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_AD_VAR_LOCUS_ISO_ALLELE, param)

    def delete_designations(self, param: Tuple[str]) -> None:
        """
        Delete all allele designations for a specific locus
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_AD_VAR_LOCUS, param)

    def delete_all_designations_of_isolate(self, param: Tuple[str]) -> None:
        """
        Delete all allele designations for a specific isolate
        :param param: isolate name
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_AD_VAR_ISO, param)

    def insert_designation_by_isolatename(self, param: Tuple[str, str, str]) -> None:
        """
        Insert allele designation for a specific isolate, locus and allele
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_AD_VAR_LOCUS_ISO_ALLELE, param)

    def insert_designation_by_isolateid(self, param: Tuple[str, str, str]) -> None:
        """
        Insert allele designation for a specific isolate, locus and allele
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_AD_VAR_LOCUS_ID_ALLELE, param)

    def update_designations(self, param: Tuple[str, str, str]) -> None:
        """
        Update allele designation for a specific isolate, locus and allele
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_ALLELE_TB_AD_VAR_LOCUS_ALLELE, param)
