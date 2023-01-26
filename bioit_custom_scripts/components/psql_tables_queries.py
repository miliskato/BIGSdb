from typing import List, Tuple, Union

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries

"""
The current file contains subclasses of the DatabaseConnection class for Bigsdb tables
Some tables are shared (duplicated) among seqdef and isolates.
Table names are PascalCase replaced by pascal_case minus Tbl
"""


class TblAlleleDesignations(DatabaseConnection):
    """
    allele_designations table in the isolates database
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self._db_type != 'isolates':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')

    def update_designations(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_ALLELE_TB_AD_VAR_LOCI_ALLELE, param)


class TblClientDbaseLoci(DatabaseConnection):
    """
    client_dbase_loci table in the seqdef database (required for rest api)
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')

    def insert_locus(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLDBLOCI_VAR_LOCUS, param)


class TblIsolates(DatabaseConnection):
    """
    isolates table in the isolates database
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self._db_type != 'isolates':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')

    def delete_isolate(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_DEL__TB_ISO_VAR_ISO_ISO, param)

    def insert_isolate(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_ISO_VAR_ISO_ISO_ISO_DATE, param)

    def revert_newversion(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_NEWV_TB_ISO_VAR_ISO, param)

    def update_newversion(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_NEWV_TB_ISO_VAR_ISO_ISO_ISO, param)


class TblLoci(DatabaseConnection):
    """
    loci table in both databases
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def count_locus(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.UNI_SEL_COUNT_TB_LOCI_VAR_LOCUS, param)

    def insert_locus_isolates(self, param: Tuple[str, str, str, str]) -> None:
        if self._db_type != 'isolates':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')
        self.execute_query(PsqlQueries.ISO_INS__TB_LOCI_VAR_LOCUS_DBNAME_DBID_URL, param)

    def insert_locus_seqdef(self, param: Tuple[str]) -> None:
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')
        self.execute_query(PsqlQueries.SEQ_INS__TB_LOCI_VAR_LOCUS, param)


class TblProfiles(DatabaseConnection):
    """
    isolates table in the isolates database
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')

    def delete_profile(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_DEL__TB_PROF_VAR_SCHEME_PROFID, param)

    def insert_profile(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROF_VAR_SCHEME_PROFID, param)

    def select_profile(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.SEQ_SEL_PROFID_TB_PROF_VAR_SCHEME, param)


class TblProfileFields(DatabaseConnection):
    """
    isolates table in the isolates database
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')

    def insert_profile_field(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROFFIELDS_VAR_SCHEME_SCHFIELD_PROFID_VALUE, param)


class TblProfileMembers(DatabaseConnection):
    """
    isolates table in the isolates database
    """
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')

    def insert_profile_field(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROFMEM_VAR_SCHEME_SCHFIELD_PROFID_VALUE, param)
"""
QUERIES
naming convention (made up by MK):
DB (seq or iso or uni (universal))
_ SEL INS UPD or DEL
what .. (any number of whats separated by _, not applicable for ins and del)
_TB WHERE  (from which table, or in which table)
_VAR WHAT (Where which parameters, any nr of which separated by _, indicator for how many arguments to pass to query)
.
Group queries by database, then by crud, then by table, then alphabetically
"""
# TB scheme members
UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
    INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
    VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
UNI_SEL_COUNT_TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
    SELECT COUNT(*) FROM scheme_members WHERE scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""

# TB sequences
SEQ_INS__TB_SEQ_VAR_LOCUS_ALL_SEQ: Final[str] = """
    INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
    VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS: Final[str] = """SELECT allele_id FROM sequences WHERE locus=%s;"""
SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS_SEQ: Final[str] = """
    SELECT allele_id FROM sequences WHERE locus=%s AND sequence=%s;"""
SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS: Final[str] = """
    SELECT COUNT(*) FROM sequences WHERE 
    locus=%s AND sequence='null allele';"""
SEQ_UPD_ALLELE_TB_SEQ_VAR_LOCUS_ALLELE: Final[str] = """
    UPDATE sequences SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""