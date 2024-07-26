from typing import Any, List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblIsolates(DatabaseConnection):
    """
    isolates table in the isolates database
    """
    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def add_validation(self, param: Tuple[str, str, str, str]) -> None:
        """
        Add validation metadata to an isolate in order for the users to be able to consult it
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_VALTYPE_VALCUR_VALDATE_TB_ISO_VAR_ID, param)

    def count_isolate(self, param: Tuple[str]) -> List[Tuple[int]]:
        """
        Counts the nr of isolates where isolate = isolate (any integer value because versioining results in
        multiple isolate entries with the same name (different id))
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: Count enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_COUNT_TB_ISO_VAR_ISO, param)

    def delete_isolate(self, param: List[str]) -> None:
        """
        Deletes the last version of an isolate
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_DEL__TB_ISO_VAR_ISO_ISO, param * 2)

    def insert_isolate(self, param: Tuple[str, str, str]) -> None:
        """
        Inserts a new isolate
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ISO_VAR_ISO_UPL_DATE, param)

    def insert_isolate_newversion(self, param: Tuple[str, str, str, str]) -> None:
        """
        Inserts a new isolate version
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_INS__TB_ISO_VAR_ISO_ISO_ISO_DATE, param)

    def revert_newversion(self, param: Tuple[str]) -> None:
        """
        Reverts the new version pointer of the latest - 1 isolate version to the latest version
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: None
        """
        self.execute_query(PsqlQueries.ISO_UPD_NEWV_TB_ISO_VAR_ISO, param)

    def select_cgsts_of_two_latest_versions_of_isolate(self, param: Tuple[int, str]) -> List[Optional[Tuple[Any]]]:
        """
        Used for isolates where multiple versions exist; selects the cgsts of the two latest versions of an isolate,
        along with the isolate ids
        :param param: cgmlst scheme id, cgmlst scheme id, isolate name
        :return: None or list of tuple isolate_id and cgst
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ID_CGST_TB_ISO_VAR_SCHID_ISO, param)

    def select_isolates_by_cgsts_and_between_dates(self, param: Tuple[int, Tuple[str, ...], str, str]) -> \
            List[Optional[Tuple[Any]]]:
        """
        Selects all current versions of isolates that belong to a set of cgsts and were isolated between a
        given set of dates.
        :param param: cgmlst scheme id, cgsts, date1 (in YYYY-MM-DD), date2 (in YYYY-MM-DD)
        :return: None or list of tuple of isolates.id, isolates.isolate, isolates.isolation_date (as datetime date), cgst
        """
        param_arranged_for_psql = (param[0], param[0], param[0], param[1], param[2], param[3])
        return self.execute_query(PsqlQueries.ISO_SEL_ID_ISO_DATE_CGST_TB_ISO_VAR_SCHID_SCHID_SCHID_CGSTS_DATE1_DATE2,
                                  param_arranged_for_psql)

    def select_isolates_by_cgsts(self, param: Tuple[int, Tuple[str, ...]]) -> List[Optional[Tuple[Any]]]:
        """
        Selects all current versions of isolates that belong to a set of cgsts
        :param param: cgmlst scheme id, cgsts
        :return: None or list of tuple of isolates.id, isolates.isolate, isolates.isolation_date (as datetime date), cgst
        """
        param_arranged_for_psql = (param[0], param[0], param[0], param[1])
        return self.execute_query(PsqlQueries.ISO_SEL_ID_ISO_DATE_CGST_TB_ISO_VAR_SCHID_SCHID_SCHID_CGSTS, param_arranged_for_psql)

    def select_isolates_by_cluster_group_and_between_dates(self, param: Tuple[int, int, str, str, str]) -> List[Optional[Tuple[Any]]]:
        """
        Selects all current versions of isolates that belong to the cluster group of a given cgst and were isolated between a
        given set of dates.
        :param param: classification_scheme_id, cgmlst scheme id, cgst,
        date1 (in YYYY-MM-DD), date2 (in YYYY-MM-DD)
        :return: None or list of tuple of isolates.id, isolates.isolate, isolates.isolation_date (as datetime date), cgst
        """
        param_arranged_for_psql = (param[0], param[1], param[1], param[0], param[0], param[0], param[0], param[2],
                                   param[3], param[4])
        return self.execute_query(
            PsqlQueries.ISO_SEL_ID_ISO_DATE_CGST_CLGR_TB_ISO_VAR_CSCHID_SCHID_SCHID_CSCHID_CSCHID_CSCHID_CSCHID_CGST_DATE1_DATE2, param_arranged_for_psql)

    def select_isolates_by_cluster_group(self, param: Tuple[int, int, str]) -> List[Optional[Tuple[Any]]]:
        """
        Selects all current versions of isolates that belong to the cluster group of a given cgst
        :param param: classification_scheme_id, cgmlst scheme id, cgst
        :return: None or list of tuple of isolates.id, isolates.isolate, isolates.isolation_date (as datetime date), cgst
        """
        param_arranged_for_psql = (param[0], param[1], param[1], param[0], param[0], param[0], param[0], param[2])
        return self.execute_query(
            PsqlQueries.ISO_SEL_ID_ISO_DATE_CGST_CLGR_TB_ISO_VAR_CSCHID_SCHID_SCHID_CSCHID_CSCHID_CSCHID_CSCHID_CGST, param_arranged_for_psql)

    def select_isolates_with_isolation_date(self, param: Tuple[Tuple[str, ...]]) -> List[Optional[Tuple[Any]]]:
        """
        Selects all current versions of isolates that appear in input list and have an isolation date; needed for temporary alerts implementation.
        :param param: isolates
        :return: None or list of tuple of isolates.isolate, isolates.isolation_date (as datetime date)
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ISO_DATE_TB_ISO_VAR_ISOS, param)

    def select_latestanalysisdate_for_isolate(self, param: Tuple[str]) -> List[Optional[Tuple[Any]]]:
        """
        Selects the latest analysis date for a given isolate
        :param param: variables to feed to the PSQL query, which also sanitizes these variables,
        necessary parameters visible in the PSQL query name and query
        :return: latest analysis date enclosed in a tuple and a list
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ANADATE_TB_ISO_VAR_ISO, param)

    def select_id_for_isolate(self, param: Tuple[str]) -> List[Tuple[Optional[int]]]:
        """
        Selects the id of the latest isolate version
        :param param: variables to feed to the PSQL query: isolate_id
        :return: natural number
        """
        return self.execute_query(PsqlQueries.ISO_SEL_ID_TB_ISO_VAR_ISO, param)

    def select_validationdate_for_isolate(self, param: Tuple[str]) -> Optional[List[Tuple[Any]]]:
        """
        Selects the last two validation dates for a given isolate
        :param param: variables to feed to the PSQL query, isolates_id
        :return: None or list of tuple of dates
        """
        return self.execute_query(PsqlQueries.ISO_SEL_VALDATES_TB_ISO_VAR_ISO, param)

    def listing_isolates(self) -> List[Tuple[str]]:
        """
        Get list of isolate currently present in isolates table of bigsdb_isolates db.
        """
        return self.execute(PsqlQueries.ISO_SEL_ISOLATE_ID)

    @staticmethod
    def build_update_nomin_metadata_query(metadata_mapping: dict[str, Any]) -> str:
        """
        Build the query used to update metadata for a specific species
        :metadata_mapping : db<->json fields mapping for the species
        :return: the update query
        """
        set_list = []
        for key in metadata_mapping:
            set_list.append(str(key + "=%s"))
        sets = ', '.join(map(str, set_list))
        return str.format(PsqlQueries.ISO_INSERT_GENERIC_LAB_METADATA_TEMPLATE, sets)

    def update_nomin_metadata(self, query: str, param: List[str]) -> None:
        """
        Adds laboratory nominative data in isolates table for the specified species
        :param query: PSQL query to be fed
        :param param: variables to feed to the PSQL query
        :return: None
        """
        self.execute_query(query, param)

