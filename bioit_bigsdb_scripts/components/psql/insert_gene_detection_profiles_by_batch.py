from datetime import date
from types import TracebackType
from typing import List, Type

import psycopg2

from .databaseconnection import DatabaseConnection

class GeneDetectionProfilesBatchData:
    """
    This class initializes the lists to store the values that will fill the db fields.
    """
    def __init__(self):
        self.loci_fields = []
        self.scheme_members_fields = []
        self.client_dbase_loci_fields = []
        self.isolates_loci_fields = []
        self.sequences_fields = []

class GeneDetectionProfilesBatchInserter:
    """
    This class opens connections to seqdef and isolates DB and performs the insertion of gene detection schemes by batch
    """
    def __init__(self, species: str) -> None:
        """
        open database connections, one to isolates and the other to the seqdef db.
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self.isolates_db_connection = DatabaseConnection(species,db_type='isolates', autocommit=False)
        self.seqdef_db_connection = DatabaseConnection(species,db_type='seqdef', autocommit=False)

    def insert(self, batch_data: GeneDetectionProfilesBatchData) -> None:
        """
        This method performs the insertion of gene detection scheme elements by batch.
        :param batch_data: GeneDetectionProfilesBatchData
        """
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

    def __insert_multiple_loci_seqdef(self, data: List) -> None:
        """
        to insert multiple loci in seqdef
        :param data: list of values to fill the sql insert statements
        :return: None
        """
        cur = self.seqdef_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s,%s,%s,%s,%s)',row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) VALUES ".format(table='loci') + args_str)

    @staticmethod
    def __insert_multiple_scheme_members(cur:psycopg2.extensions.cursor, data: List) -> None:
        """
        to insert multiple scheme_members
        :param data: list of values to fill the sql insert statements
        :return: None
        """
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s)',row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (scheme_id, locus, curator, datestamp) VALUES ".format(table='scheme_members') + args_str)

    def __insert_multiple_loci_client_db(self, data: List) -> None:
        """
        to insert multiple loci in client db
        :param data: list of values to fill the sql insert statements
        :return: None
        """
        cur=self.seqdef_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s)', row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (client_dbase_id, locus, curator, datestamp) VALUES ".format(table='client_dbase_loci')+args_str)

    def __insert_multiple_loci_isolates(self, data: List) -> None:
        """
        to insert multiple loci in isolates
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        cur = self.isolates_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)', row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, url, isolate_display, main_display, query_field, analysis, submission_template, curator, date_entered, datestamp) VALUES ".format(table='loci') + args_str)

    def __insert_multiple_sequences(self, data: List) -> None:
        """
        inserts multiple sequences for a given allele and locus
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        cur = self.seqdef_db_connection._cursor
        args_str = ','.join(cur.mogrify('(%s, %s, %s, %s, %s, %s, %s, %s)',row).decode("utf-8") for row in data)
        cur.execute("INSERT INTO {table} (locus, allele_id, sequence, status, sender,curator, date_entered, datestamp) VALUES ".format(table='sequences')+args_str)

    def __enter__(self):
        """enter the runtime context related to the class (interest: connections)"""
        return self

    def __exit__(self, exc_type: Type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """close the db connections at the end of the run"""
        self.isolates_db_connection.close()
        self.seqdef_db_connection.close()