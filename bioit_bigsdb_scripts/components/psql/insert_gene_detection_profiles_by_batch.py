from types import TracebackType
from typing import Type

from .databaseconnection import DatabaseConnection

class GeneDetectionProfilesBatchData:
    def __init__(self):
        self.loci_fields = []
        self.scheme_members_fields = []
        self.client_dbase_loci_fields = []
        self.isolates_loci_fields = []
        self.sequences_fields = []

class GeneDetectionProfilesBatchInserter:
    """
    This class opens connections to seqdef and isolates DB and performs the instertion of gene detection schemes by batch
    """
    def __init__(self, species: str) -> None:
        """
        open database connections, one to isolates and the other to the seqdef db.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self.isolates_db_connection = DatabaseConnection(species,db_type='isolates', autocommit=False)
        self.seqdef_db_connection = DatabaseConnection(species,db_type='seqdef', autocommit=False)

    def insert(self, batch_data: GeneDetectionProfilesBatchData) -> None:
        try:
            self.__insert_multiple_loci_seqdef(batch_data.loci_fields)
            self.__insert_multiple_scheme_members(self.seqdef_db_connection._cursor ,batch_data.scheme_members_fields)
            self.__insert_multiple_loci_client_db(batch_data.client_dbase_loci_fields)
            self.__insert_multiple_loci_isolates(batch_data.isolates_loci_fields)
            self.__insert_multiple_scheme_members(self.isolates_db_connection._cursor, batch_data.scheme_members_fields)
            self.__insert_multiple_sequences(batch_data.sequences_fields)

            self.seqdef_db_connection._connection.commit()
            self.isolates_db_connection._connection.commit()
        except Exception:
            self.seqdef_db_connection._connection.rollback()
            self.isolates_db_connection._connection.rollback()
            # TODO raise Exception()

    def __insert_multiple_loci_seqdef(self, data) -> None:
        """
        to insert multiple loci in seqdef
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        cur = self.seqdef_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s,%s,%s,%s,%s)',row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO loci (id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) VALUES " + args_str)

    def __insert_multiple_scheme_members(self, cur, data):
        """
        to insert multiple scheme_members
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s)',row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (scheme_id, locus, curator, datestamp) VALUES ".format(table='scheme_members') + args_str)

    def __insert_multiple_loci_client_db(self, data) -> None:
        """
        to insert multiple loci
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        cur=self.seqdef_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s)', row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (client_dbase_id, locus, curator, datestamp) VALUES ".format(table='client_dbase_loci')+args_str)

    def __insert_multiple_loci_isolates(self, data) -> None:
        """
        to insert multiple loci in isolates
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        cur = self.isolates_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, url, isolate_display, main_display, query_field, analysis, submission_template, curator, date_entered, datestamp) VALUES ".format(table='loci') + args_str)

    def __insert_multiple_sequences(self, data) -> None:
        """
        inserts multiple sequences for a given allele and locus
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        cur = self.seqdef_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s, %s, %s, %s, %s, %s, %s, %s)',row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (locus, allele_id, sequence, status, sender,curator, date_entered, datestamp) VALUES ".format(table='sequences')+args_str)

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        self.isolates_db_connection.close()
        self.seqdef_db_connection.close()