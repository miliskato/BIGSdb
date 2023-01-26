from typing import Any, Dict, List, Union

import psycopg2.extensions

from .databaseconnection import DatabaseConnection


class JsonSuperClass:
    """
    Class containing definitions to insert json typing and gene detection results
    """

    def __init__(self, isolatename: str, species: str, isolates_psql_db: DatabaseConnection, seqdef_psql_db: DatabaseConnection,
                 sample_output_dict: Dict[str, Any], config_data: Dict[str, Any]) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param isolates_psql_db: isolate database connection instance
        :param seqdef_psql_db: sequence definition database connection instance
        :param sample_output_dict: results of sample
        :param config_data: the bigsdb config data
        :return: None
        """
        self.isolatename = isolatename
        self.species = species
        self.isolates_psql_db = isolates_psql_db
        self.seqdef_psql_db = seqdef_psql_db
        self.sample_output_dict = sample_output_dict
        self.config_data = config_data

    def _insert_allele_designation(self, locus: str, allele_id: str) -> None:
        """
        inserts given allele designations for given loci
        :param locus: locus name
        :param allele_id: allele id (often integers but can be string, but string in sql so treated as such)
        :return: None
        """
        sqlquery = """
                   INSERT INTO allele_designations(locus, isolate_id, 
                   allele_id, status, method, sender, 
                   curator, date_entered, datestamp) 
                   VALUES(%s, (SELECT MAX(id) FROM isolates WHERE isolate=%s), 
                   %s, 'confirmed', 'automatic', 1, 
                   1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
        self.isolates_psql_db.execute_query(sqlquery, (locus, self.isolatename, allele_id))

    def _insert_ad_if_needed(self, locus: str, allele_id: str) -> None:
        """
        Inserts given allele designations for given loci if they have not been inserted yet (especially useful for gene detection where multiple hits for the same locus can be found)
        :param locus: locus name
        :param allele_id: allele id (often integers but can be string, but string in sql so treated as such)
        :return: None
        """
        sqlquery = """
                   SELECT COUNT(*) FROM allele_designations WHERE 
                   locus=%s AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s) AND allele_id=%s;"""
        self.isolates_psql_db.execute_query(sqlquery, (locus, self.isolatename, allele_id))
        designationpresent: List[List[int]] = self.isolates_psql_db.fetchall()
        if designationpresent[0][0] == 0:
            self._insert_allele_designation(locus, allele_id)

    def _insert_metadata(self, field: str, value: str) -> None:
        """
        Insert given metadata (value) for given text metadata fields
        :param field: sql field value
        :param value: sql column value
        :return: None
        """
        sqlquery = """
                   INSERT INTO eav_text(isolate_id, field, value) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""
        self.isolates_psql_db.execute_query(sqlquery, (self.isolatename, field, value))

    def _insert_metadata_hidden(self, field: str, value: str) -> None:
        """
        Insert given hidden metadata (value) for given hidden text metadata fields
        :param field: sql field value
        :param value: sql column value
        :return: None
        """
        sqlquery = """
                   INSERT INTO eav_text_hidden(isolate_id, field, value) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""
        self.isolates_psql_db.execute_query(sqlquery, (self.isolatename, field, value))

    def _insert_metadata_bool(self, field: str, value: str) -> None:
        """
        Insert given metadata (value) for given boolean metadata fields
        :param field: sql field value
        :param value: sql column value
        :return: None
        """
        sqlquery = """
                   INSERT INTO eav_boolean(isolate_id, field, value) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""
        self.isolates_psql_db.execute_query(sqlquery, (self.isolatename, field, value))

    def _insert_dummy_sequence_if_needed(self, locus: str, allele_id: str) -> None:
        """
        Allele designations for non existing sequences are allowed BUT when clicking on them, a not found error will be received.
        In order to circumvent this, dummy alleles (multitudes of TAG) are inserted; this way users can still see which other samples have this allele designation
        Mostly used in gene detection schemes and other custom non-typing schemes.
        :param locus: locus name
        :param allele_id: allele id (often integers but can be string, but string in sql so treated as such)
        :return:
        """
        sqlquery = """SELECT COUNT(*) FROM sequences WHERE allele_id=%s and locus=%s;"""
        self.seqdef_psql_db.execute_query(sqlquery, (allele_id, locus))
        present: List[List[int]] = self.seqdef_psql_db.fetchall()
        if present[0][0] == 0:
            sqlquery = """SELECT sequence FROM sequences WHERE locus=%s ORDER BY CHAR_LENGTH(sequence) DESC, sequence DESC LIMIT 1;"""
            self.seqdef_psql_db.execute_query(sqlquery, (locus,))
            highest_dummy_sequence: List[List[str]] = self.seqdef_psql_db.fetchall()
            dummysequence: str = 'dummy_1' if len(highest_dummy_sequence) == 0 else '_'.join(['dummy', int(highest_dummy_sequence[0][0].split('_')[1]) + 1])
            sqlquery = """
                       INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) 
                       VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
            self.seqdef_psql_db.execute_query(sqlquery, (locus, allele_id, dummysequence))
        # could also add insert allele designation here but i prefer to keep these definitions separate for readability

    def _insert_locus_if_needed(self, locus: str, scheme: str) -> None:
        """
        Inserts a given locus and assigns it to a given scheme, if not yet existing
        :param locus: locus name
        :param scheme: scheme name in bigsdb
        :return: None
        """
        sqlquery = """SELECT COUNT(*) FROM loci WHERE id=%s"""
        self.seqdef_psql_db.execute_query(sqlquery, (locus,))
        present: List[List[int]] = self.seqdef_psql_db.fetchall()
        if present[0][0] == 0:
            # insert into seqdef
            sqlquery = """
                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) 
                       VALUES(%s, 'DNA', 'text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
            self.seqdef_psql_db.execute_query(sqlquery, (locus,))
            sqlquery_members = """
                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
            self.seqdef_psql_db.execute_query(sqlquery_members, (scheme, locus))
            sqlquery = """
                       INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) 
                       VALUES(1, %s, 1, (SELECT CURRENT_DATE));"""
            self.seqdef_psql_db.execute_query(sqlquery, (locus,))

            # insert into isolates
            dbaseurl: str = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{self.species}_seqdef',
                                '&page=alleleInfo&locus=', f"{locus}", '&allele_id=[?]'])
            sqlquery = """
                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, 
                       url, isolate_display, main_display, query_field, analysis, submission_template, 
                       curator, date_entered, datestamp) 
                       VALUES(%s, 'DNA', 'text', 't', 't', %s, %s, 
                       %s, 'allele_only', 'f', 't', 't', 'f', 
                       1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
            self.isolates_psql_db.execute_query(sqlquery, (locus, f'bigsdb_{self.species}_seqdef', locus, dbaseurl))
            self.isolates_psql_db.execute_query(sqlquery_members, (scheme, locus))

    def _assign_schememember_if_needed(self, locus: str, scheme: str) -> None:
        """
        Assign given locus to given scheme if not yet in there. Necessary in case loci belong to multiple schemes (although often in that case theyll have a different name).
        :param locus: locus name
        :param scheme: scheme name in bigsdb
        :return: None
        """
        sqlquery = """
                   SELECT COUNT(*) FROM scheme_members WHERE 
                   scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""
        self.seqdef_psql_db.execute_query(sqlquery, (scheme, locus))
        schemememberpresent: List[List[int]] = self.seqdef_psql_db.fetchall()
        if schemememberpresent[0][0] == 0:
            sqlquery = """
                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
            self.seqdef_psql_db.execute_query(sqlquery, (scheme, locus))
            self.isolates_psql_db.execute_query(sqlquery, (scheme, locus))

    def _insert_history(self, message: str) -> None:
        """
        Inserts the given message into the history for the current isolate
        :param message: message that should be displayed in the sample's history
        :return: None
        """
        sqlquery = """
                   INSERT INTO history(isolate_id, timestamp, action, curator) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s),(SELECT NOW()::TIMESTAMP), %s, 1);"""
        self.isolates_psql_db.execute_query(sqlquery, (self.isolatename, message))
