class JsonSuperClass:
    """
    Class containing definition to insert typing results
    """
    def __init__(self, isolatename, species, cur_isolates, cur_seqdef, outputjsondict):
        self.isolatename = isolatename
        self.species = species
        self.cur_isolates = cur_isolates
        self.cur_seqdef = cur_seqdef
        self.outputjsondict = outputjsondict

    def _insert_allele_designation(self, locus, allele_id):
        self.cur_isolates.execute(f"INSERT INTO allele_designations(locus, isolate_id, "
                                  f"allele_id, status, method, sender, "
                                  f"curator, date_entered, datestamp) "
                                  f"VALUES('{locus}', (SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'), "
                                  f"'{allele_id}', 'confirmed', 'automatic', 1, "
                                  f"1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")

    def _insert_AD_if_needed(self, locus, allele_id):
        self.cur_isolates.execute(f"SELECT COUNT(*) FROM allele_designations WHERE "
                                  f"locus='{locus}' AND allele_id='{allele_id}' AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}')")
        designationpresent = self.cur_isolates.fetchall()
        if designationpresent[0][0] == 0:
            self._insert_allele_designation(locus, allele_id)

    def _insert_metadata(self, field, value):
        self.cur_isolates.execute(f"INSERT INTO eav_text(isolate_id, "
                                  f"field, value)"
                                  f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'),"
                                  f"'{field}', '{value}') ")

    def _insert_metadata_bool(self, field, value):
        self.cur_isolates.execute(f"INSERT INTO eav_boolean(isolate_id, "
                                  f"field, value)"
                                  f"VALUES((SELECT MAX(id) FROM isolates WHERE isolate='{self.isolatename}'),"
                                  f"'{field}', '{value}') ")

    def _insert_dummy_sequence_if_needed(self, locus, allele_id):
        self.cur_seqdef.execute(
            f"SELECT allele_id FROM sequences WHERE allele_id = '{allele_id}' and locus = '{locus}'")
        present = self.cur_seqdef.fetchall()
        if present == []:
            self.cur_seqdef.execute(
                f"SELECT sequence FROM sequences WHERE locus  ='{locus}' ORDER BY CHAR_LENGTH(sequence) DESC LIMIT 1")
            longest_dummy_sequence = self.cur_seqdef.fetchall()
            if longest_dummy_sequence == []:
                dummysequence = 'TAG'
            else:
                dummysequence = ''.join([longest_dummy_sequence[0][0], 'TAG'])
            self.cur_seqdef.execute(f"INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
                                      VALUES('{locus}','{allele_id}','{dummysequence}','unchecked',1,1,(SELECT CURRENT_DATE),(SELECT CURRENT_DATE))")
        # could also add insert allele designation here but i prefer to keep these definitions separate for readability

    def _insert_locus_if_needed(self, locus, scheme):
        self.cur_seqdef.execute(f"SELECT id FROM loci WHERE "
                                f"id='{locus}'")
        present = self.cur_seqdef.fetchall()
        if present == []:
            # insert into seqdef
            self.cur_seqdef.execute(f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) \
                                      VALUES('{locus}','DNA','text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
            self.cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                      VALUES((SELECT id FROM schemes WHERE name='{scheme}'), '{locus}', 1, (SELECT CURRENT_DATE))")
            self.cur_seqdef.execute(f"INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) \
                                      VALUES(1, '{locus}', 1, (SELECT CURRENT_DATE))")
            # insert into isolates
            dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{self.species}_seqdef',
                                '&page=alleleInfo&locus=', f"{locus}", '&allele_id=[?]'])
            self.cur_isolates.execute(
                f"INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, "
                f"url, isolate_display, main_display, query_field, analysis, submission_template, "
                f"curator, date_entered, datestamp) \
                  VALUES('{locus}','DNA','text', 't', 't', 'bigsdb_{self.species}_seqdef', '{locus}', "
                f"'{dbaseurl}', 'allele_only', 'f', 't', 't', 'f',"
                f" 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE))")
            self.cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                                                      VALUES((SELECT id FROM schemes WHERE name='{scheme}'), '{locus}', 1, (SELECT CURRENT_DATE))")

    def _assign_schememember_if_needed(self, locus, scheme):
        self.cur_seqdef.execute(f"SELECT COUNT(*) FROM scheme_members WHERE "
                                f"locus='{locus}' AND scheme_id=(SELECT id FROM schemes WHERE name='{scheme}')")
        schemememberpresent = self.cur_seqdef.fetchall()
        if schemememberpresent[0][0] == 0:
            self.cur_seqdef.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                      VALUES((SELECT id FROM schemes WHERE name='{scheme}'), '{locus}', 1, (SELECT CURRENT_DATE))")
            self.cur_isolates.execute(f"INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) \
                                        VALUES((SELECT id FROM schemes WHERE name='{scheme}'), '{locus}', 1, (SELECT CURRENT_DATE))")


