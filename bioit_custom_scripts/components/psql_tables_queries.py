from typing import Any, List, Tuple, Union

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
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def count_designations(self, param: Tuple[str, str, str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_AD_VAR_LOCUS_ISO_ALLELE, param)

    def delete_designations(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_DEL__TB_AD_VAR_LOCUS, param)

    def insert_designation(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_AD_VAR_LOCUS_ISO_ALLELE, param)

    def update_designations(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_ALLELE_TB_AD_VAR_LOCUS_ALLELE, param)


class TblClientDbaseLoci(DatabaseConnection):
    """
    client_dbase_loci table in the seqdef database (required for rest api)
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_locus(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLDBLOCI_VAR_LOCUS, param)


class TblEavBoolean(DatabaseConnection):
    """
    allele_designations table in the isolates database
    """

    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_eav_isolate(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVB_VAR_ISO_FIELD_VAL, param)

class TblEavText(DatabaseConnection):
    """
    allele_designations table in the isolates database
    """

    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def delete_eav(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_DEL__TB_EAVT_VAR_ID_FIELD, param)

    def insert_eav_id(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVT_VAR_ID_FIELD_VAL, param)

    def insert_eav_isolate(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVT_VAR_ISO_FIELD_VAL, param)


class TblEavTextHidden(DatabaseConnection):
    """
    allele_designations table in the isolates database
    """

    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_hidden_isolate(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVTH_VAR_ISO_FIELD_VAL, param)

    def select_hidden(self, param: Tuple[str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.ISO_SEL_ID_VAL_ISO_TB_EAVTH_VAR_FIELD, param)


class TblHistory(DatabaseConnection):
    """
    allele_designations table in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_history_id(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_HIST_VAR_ID_MESS, param)

    def insert_history_isolate(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_HIST_VAR_ISO_MESS, param)

class TblIsolates(DatabaseConnection):
    """
    isolates table in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def count_isolate(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_ISO_VAR_ISO, param)

    def delete_isolate(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_DEL__TB_ISO_VAR_ISO_ISO, param)

    def insert_isolate(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_ISO_VAR_ISO_ISO_ISO_DATE, param)

    def revert_newversion(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_NEWV_TB_ISO_VAR_ISO, param)

    def update_newversion(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_NEWV_TB_ISO_VAR_ISO_ISO_ISO, param)


class TblLoci(DatabaseConnection):
    """
    loci table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        if self._db_type != 'seqdef' and self._db_type != 'isolates':
            raise ValueError('no such database type')
        super().__init__(species, db_type)

    def count_locus(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.UNI_SEL_COUNT_TB_LOCI_VAR_LOCUS, param)

    def insert_locus_isolates(self, param: Tuple[str, str, str, str]) -> None:
        if self._db_type != 'isolates':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')
        self.execute_query(PsqlQueries.ISO_INS__TB_LOCI_VAR_LOCUS_DBNAME_DBID_URL, param)

    def insert_locus_seqdef(self, param: Tuple[str]) -> None:
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')
        self.execute_query(PsqlQueries.SEQ_INS__TB_LOCI_VAR_LOCUS, param)

class TblLocusDescriptions(DatabaseConnection):
    """
    loci table in both databases
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def delete_locus_description(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.SEQ_DEL__TB_LOCDES_VAR_LOCUS, param)

    def insert_locus_description(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_LOCDES_VAR_LOCUS_PROD_DES, param)

class TblProfiles(DatabaseConnection):
    """
    profiles table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def delete_profile(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_DEL__TB_PROF_VAR_SCHEME_PROFID, param)

    def insert_profile(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROF_VAR_SCHEME_PROFID, param)

    def select_profile(self, param: Tuple[str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_PROFID_TB_PROF_VAR_SCHEME, param)


class TblProfileFields(DatabaseConnection):
    """
    profile_fields table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_profile_field(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROFFIELDS_VAR_SCHEME_SCHFIELD_PROFID_VALUE, param)


class TblProfileMembers(DatabaseConnection):
    """
    profile_members table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_profile_member(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROFMEM_VAR_SCHEME_SCHFIELD_PROFID_VALUE, param)


class TblSchemeMembers(DatabaseConnection):
    """
    scheme_members table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        if self._db_type != 'seqdef' and self._db_type != 'isolates':
            raise ValueError('no such database type')
        super().__init__(species, db_type)

    def count_scheme_member(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS, param)

    def insert_scheme_member(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS, param)


class TblSequences(DatabaseConnection):
    """
    sequences table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def count_sequence_null(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS, param)

    def count_sequence_allele(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS_ALLELE, param)

    def insert_sequence(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_SEQ_VAR_LOCUS_ALLELE_SEQ, param)

    def select_allele_from_locus(self, param: Tuple[str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS, param)

    def select_sequence_from_locus(self, param: Tuple[str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_SEQUENCE_TB_SEQ_VAR_LOCUS, param)

    def select_allele_from_sequence(self, param: Tuple[str, str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS_SEQ, param)

    def update_alleleid(self, param: Tuple[str, str, str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.SEQ_UPD_ALLELE_TB_SEQ_VAR_LOCUS_ALLELE, param)


class TblSequenceBin(DatabaseConnection):
    """
    sequence_bin in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def count_sequencebin(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_COUNT_TB_SEQBIN_VAR_ISO, param)

    def insert_sequencebin(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_SEQBIN_VAR_ISO_SEQ_NAME, param)


class TblSubmissions(DatabaseConnection):
    """
    submissions table in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def select_closed_submissions(self) -> List[Tuple[Any]]:
        return self.execute(PsqlQueries.ISO_SEL_ID_VALUE_OUTCOME_EMAIL_TYPE_TB_SUB_VAR_)

    def update_submission(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_STATUS_TB_SUB_VAR_ID, param)