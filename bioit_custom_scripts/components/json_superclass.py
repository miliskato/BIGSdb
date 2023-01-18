import psycopg2

class JsonSuperClass:
    """
    Class containing definitions to insert json typing and gene detection results
    """
    def __init__(self, isolatename: str, species: str, cur_isolates: psycopg2.extensions.cursor, cur_seqdef: psycopg2.extensions.cursor, sample_output_dict: dict) -> None:
        """
        :param isolatename:
        :param species: commonly used bioit species name: either genus or specific like stec
        :param cur_isolates: isolate database connection object
        :param cur_seqdef: sequence definition database connection object
        :param sample_output_dict: results of sample
        """
        self.isolatename = isolatename
        self.species = species
        self.cur_isolates = cur_isolates
        self.cur_seqdef = cur_seqdef
        self.sample_output_dict = sample_output_dict

    def _insert_allele_designation(self, locus: str, allele_id: str) -> None:
        """
        inserts given allele designations for given loci
        :param locus:
        :param allele_id:
        :return:
        """
        sqlquery = """
                   INSERT INTO allele_designations(locus, isolate_id, 
                   allele_id, status, method, sender, 
                   curator, date_entered, datestamp) 
                   VALUES(%s, (SELECT MAX(id) FROM isolates WHERE isolate=%s), 
                   %s, 'confirmed', 'automatic', 1, 
                   1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
        self.cur_isolates.execute(sqlquery, (locus, self.isolatename, allele_id))

    def _insert_AD_if_needed(self, locus: str, allele_id: str) -> None:
        """
        Inserts given allele designations for given loci if they have not been inserted yet (especially useful for gene detection where multiple hits for the same locus can be found)
        :param locus:
        :param allele_id:
        :return:
        """
        sqlquery = """
                   SELECT COUNT(*) FROM allele_designations WHERE 
                   locus=%s AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s) AND allele_id=%s;"""
        self.cur_isolates.execute(sqlquery, (locus, self.isolatename, allele_id))
        designationpresent = self.cur_isolates.fetchall()
        if designationpresent[0][0] == 0:
            self._insert_allele_designation(locus, allele_id)

    def _insert_metadata(self, field: str, value: str) -> None:
        """
        Insert given metadata (value) for given text metadata fields
        :param field:
        :param value:
        :return:
        """
        sqlquery = """
                   INSERT INTO eav_text(isolate_id, field, value) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""
        self.cur_isolates.execute(sqlquery, (self.isolatename, field, value))

    def _insert_metadata_hidden(self, field: str, value: str) -> None:
        """
        Insert given hidden metadata (value) for given hidden text metadata fields
        :param field:
        :param value:
        :return:
        """
        sqlquery = """
                   INSERT INTO eav_text_hidden(isolate_id, field, value) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""
        self.cur_isolates.execute(sqlquery, (self.isolatename, field, value))

    def _insert_metadata_bool(self, field: str, value: str) -> None:
        """
        Insert given metadata (value) for given boolean metadata fields
        :param field:
        :param value:
        :return:
        """
        sqlquery = """
                   INSERT INTO eav_boolean(isolate_id, field, value) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""
        self.cur_isolates.execute(sqlquery, (self.isolatename, field, value))

    def _insert_dummy_sequence_if_needed(self, locus: str, allele_id: str) -> None:
        """
        Allele designations for non existing sequences are allowed BUT when clicking on them, a not found error will be received.
        In order to circumvent this, dummy alleles (multitudes of TAG) are inserted; this way users can still see which other samples have this allele designation
        Mostly used in gene detection schemes and other custom non-typing schemes.
        :param locus:
        :param allele_id:
        :return:
        """
        sqlquery = """SELECT allele_id FROM sequences WHERE allele_id=%s and locus=%s;"""
        self.cur_seqdef.execute(sqlquery, (allele_id, locus))
        present = self.cur_seqdef.fetchall()
        if present == []:
            sqlquery = """SELECT sequence FROM sequences WHERE locus=%s ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1;"""
            self.cur_seqdef.execute(sqlquery, (locus,))
            longest_dummy_sequence = self.cur_seqdef.fetchall()
            if longest_dummy_sequence == []:
                dummysequence = 'TAG'
            else:
                dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
            sqlquery = """
                       INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) 
                       VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
            self.cur_seqdef.execute(sqlquery, (locus, allele_id, dummysequence))
        # could also add insert allele designation here but i prefer to keep these definitions separate for readability

    def _insert_locus_if_needed(self, locus: str, scheme: str) -> None:
        """
        Inserts a given locus and assigns it to a given scheme, if not yet existing
        :param locus:
        :param scheme:
        :return:
        """
        sqlquery = """SELECT id FROM loci WHERE id=%s"""
        self.cur_seqdef.execute(sqlquery, (locus,))
        present = self.cur_seqdef.fetchall()
        if present == []:
            # insert into seqdef
            sqlquery = """
                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) 
                       VALUES(%s, 'DNA', 'text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
            self.cur_seqdef.execute(sqlquery, (locus,))
            sqlquery_members = """
                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
            self.cur_seqdef.execute(sqlquery_members, (scheme, locus))
            sqlquery = """
                       INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) 
                       VALUES(1, %s, 1, (SELECT CURRENT_DATE));"""
            self.cur_seqdef.execute(sqlquery, (locus,))

            # insert into isolates
            dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{self.species}_seqdef',
                                '&page=alleleInfo&locus=', f"{locus}", '&allele_id=[?]'])
            sqlquery = """
                       INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, 
                       url, isolate_display, main_display, query_field, analysis, submission_template, 
                       curator, date_entered, datestamp) 
                       VALUES(%s, 'DNA', 'text', 't', 't', %s, %s, 
                       %s, 'allele_only', 'f', 't', 't', 'f', 
                       1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
            self.cur_isolates.execute(sqlquery, (locus, f'bigsdb_{self.species}_seqdef', locus, dbaseurl))
            self.cur_isolates.execute(sqlquery_members, (scheme, locus))

    def _assign_schememember_if_needed(self, locus: str, scheme: str) -> None:
        """
        Assign given locus to given scheme if not yet in there. Necessary in case loci belong to multiple schemes (although often in that case theyll have a different name).
        :param locus:
        :param scheme:
        :return:
        """
        sqlquery = """
                   SELECT COUNT(*) FROM scheme_members WHERE 
                   scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""
        self.cur_seqdef.execute(sqlquery, (scheme, locus))
        schemememberpresent = self.cur_seqdef.fetchall()
        if schemememberpresent[0][0] == 0:
            sqlquery = """
                       INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
                       VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
            self.cur_seqdef.execute(sqlquery, (scheme, locus))
            self.cur_isolates.execute(sqlquery, (scheme, locus))

    def _insert_history(self, message: str) -> None:
        """
        Inserts the given message into the history for the current isolate
        :param self:
        :param message:
        :return:
        """
        sqlquery = """
                   INSERT INTO history(isolate_id, timestamp, action, curator) 
                   VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s),(SELECT NOW()::TIMESTAMP), %s, 1);"""
        self.cur_isolates.execute(sqlquery, (self.isolatename, message))
