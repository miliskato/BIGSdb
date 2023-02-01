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


class TblClassificationGroups(DatabaseConnection):
    """
    classification_groupstable in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def count_group(self, param: Tuple[str, str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.SEQ_INS__TB_CLGR_VAR_CGSCHID_GRID, param)

    def inactivate_group(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_UPD_ACTIVE_TB_CLGR_VAR_CGSCHID_GRID, param)

    def insert_group(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_SEL_COUNT_TB_CLGR_VAR_CGSCHID_GRID, param)


class TblClassificationGroupProfiles(DatabaseConnection):
    """
    classification_group_profiles table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_profile(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLGRPR_VAR_CGSCHID_GRID_PRID_SCHEME, param)

    def select_profile_group(self, param: Tuple[str, str]) -> Union[None, List[Tuple[int]]]:
        return self.execute_query(PsqlQueries.SEQ_SEL_GRID_TB_CLGRPR_VAR_CGSCHID_PRID, param)

    def update_profile_group(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_UPD_GRID_TB_CLGRPR_VAR_CGSCHID_PRID, param)

class TblClassificationGroupProfileHistory(DatabaseConnection):
    """
    classification_group_profiles_history table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_history(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLGRPRHIST_VAR_SCHEME_PRID_CGSCHID_PREVGR, param)

class TblClassificationSchemes(DatabaseConnection):
    """
    classification_schemes table in both databases
    """
    def __init__(self, species: str, db_type: str) -> None:
        if self._db_type != 'seqdef' and self._db_type != 'isolates':
            raise ValueError('no such database type')
        super().__init__(species, db_type)

    def insert_cgscheme_isolates(self, param: Tuple[str, str, str, str, str, str, str]) -> None:
        if self._db_type != 'isolates':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')
        self.execute_query(PsqlQueries.ISO_INS__TB_CLSCH_VAR_CGSCHID_SCHEME_NAME_DESC_INCTHR_CGSCHID_CGSCHID, param)

    def insert_cgscheme_seqdef(self, param: Tuple[str, str, str, str, str, str]) -> None:
        if self._db_type != 'seqdef':
            raise ValueError(f'Wrong db_type {self._db_type}for the current table object/instance')
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLSCH_VAR_CGSCHID_SCHEME_NAME_DESC_INCTHR_CGSCHID, param)

    def select_cgschemes(self) -> Union[None, List[Tuple[str, str]]]:
        return self.execute(PsqlQueries.SEQ_SEL_CGSCHID_INCTHR_TB_CLSCH_VAR_)

class TblClientDbaseLoci(DatabaseConnection):
    """
    client_dbase_loci table in the seqdef database (required for rest api)
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        super().__init__(species, self._db_type)

    def insert_locus(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_CLGRPRHIST_VAR_SCHEME_PRID_CGSCHID_PREVGR, param)


class TblEavFields(DatabaseConnection):
    """
    eav_fields table in the isolates database
    """

    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_fields_16s(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVF_VAR_FIELD, param)

    def select_fields_amr(self) -> List[Tuple[str]]:
        return self.execute(PsqlQueries.ISO_SEL_FIELD_TB_EAVF_VAR_)

    def select_fields_like(self, param: Tuple[str]) -> List[Tuple[str]]:
        return self.execute_query(PsqlQueries.ISO_SEL_FIELD_TB_EAVF_VAR_FIELD, param)

    def select_count_16s(self, param: Tuple[str]) -> List[Tuple[str]]:
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_EAVF_VAR_FIELD, param)


class TblEavBoolean(DatabaseConnection):
    """
    eav_boolean table in the isolates database
    """

    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_eav_isolate(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVB_VAR_ISO_FIELD_VAL, param)

class TblEavText(DatabaseConnection):
    """
    eav_text table in the isolates database
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
    eav_text_hidden table in the isolates database
    """

    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_hidden_isolate(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_EAVTH_VAR_ISO_FIELD_VAL, param)

    def select_hidden(self, param: Tuple[str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.ISO_SEL_ID_VAL_ISO_TB_EAVTH_VAR_FIELD, param)

    def select_mongo_resultsversion(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.ISO_SEL_VERSION_TB_EAVTH_VAR_ISO, param)


class TblHistory(DatabaseConnection):
    """
    history table in the isolates database
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

    def add_validation(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query((PsqlQueries.ISO_UPD_VALTYPE_VALCUR_VALDATE_VAR_ID, param))

    def count_isolate(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_ISO_VAR_ISO, param)

    def delete_isolate(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_DEL__TB_ISO_VAR_ISO_ISO, param)

    def insert_isolate(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_ISO_VAR_ISO_UPL_DATE, param)

    def insert_isolate_newversion(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_ISO_VAR_ISO_ISO_ISO_DATE, param)

    def revert_newversion(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_NEWV_TB_ISO_VAR_ISO, param)

    def select_latestanalysisdate_for_isolate(self, param: Tuple[str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.ISO_SEL_ANADATE_TB_ISO_VAR_ISO, param)

    def select_maxid_for_isolate(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.ISO_SEL_MAXID_TB_ISO_VAR_ISO, param)

    def select_validationdate_for_isolate(self, param: Tuple[str]) -> List[Tuple[Any]]:
        return self.execute_query(PsqlQueries.ISO_SEL_VALDATES_TB_ISO_VAR_ISO, param)

    def update_newversion(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_NEWV_TB_ISO_VAR_ISO_ISO_ISO, param)


class TblIsolateSubmissionFieldOrder(DatabaseConnection):
    """
    isolate_submission_field_order table in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_validation_indexes(self, param: Tuple[str, int]) -> None:
        self.execute_query((PsqlQueries.ISO_INS__TB_ISOSUBFO_VAR_FIELD_INDEX, param))


class TblIsolateSubmissionIsolates(DatabaseConnection):
    """
    isolate_submission_isolates table in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_validation_metadata(self, param: Tuple[str, str]) -> None:
        self.execute_query((PsqlQueries.ISO_INS__TB_ISOSUBISO_VAR_FIELD_VALUE, param))


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
    locus_descriptions table in both databases
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
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

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
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

    def insert_profile_field(self, param: Tuple[str, str, str, str]) -> None:
        self.execute_query(PsqlQueries.SEQ_INS__TB_PROFFIELDS_VAR_SCHEME_SCHFIELD_PROFID_VALUE, param)


class TblProfileMembers(DatabaseConnection):
    """
    profile_members table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

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

    def select_loci_amr(self) -> List[Tuple[str]]:
        return self.execute(PsqlQueries.UNI_SEL_LOCUS_TB_SCHMEM_VAR_)


class TblSequences(DatabaseConnection):
    """
    sequences table in the seqdef database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'seqdef'
        self._autocommit = True
        super().__init__(species, self._db_type, autocommit=self._autocommit)

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
    sequence_bin in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def count_sequencebin(self, param: Tuple[str]) -> List[Tuple[int]]:
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_SEQBIN_VAR_ISO, param)

    def insert_sequencebin(self, param: Tuple[str, str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_SEQBIN_VAR_ISO_SEQ_NAME, param)

    def update_sequencebin_newversion(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD__TB_SEQBIN_VAR_ISO_ISO, param)

    def revert_sequencebin_newversion(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_REVERSE_TB_SEQBIN_VAR_ISO_ISO, param)


class TblSeqBinStats(DatabaseConnection):
    """
    seqbin_stats in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def update_seqbinstats_newversion(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD__TB_SEQBINSTATS_VAR_ISO_ISO, param)

    def revert_seqbinstats_newversion(self, param: Tuple[str, str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_REVERSE_TB_SEQBINSTATS_VAR_ISO_ISO, param)


class TblSubmissions(DatabaseConnection):
    """
    submissions table in the isolates database
    """
    def __init__(self, species: str) -> None:
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def insert_submission(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_INS__TB_SUB_VAR_VALTYPE, param)

    def select_closed_submissions(self) -> List[Tuple[Any]]:
        return self.execute(PsqlQueries.ISO_SEL_ID_VALUE_OUTCOME_EMAIL_TYPE_TB_SUB_VAR_)

    def update_submission(self, param: Tuple[str]) -> None:
        self.execute_query(PsqlQueries.ISO_UPD_STATUS_TB_SUB_VAR_ID, param)
