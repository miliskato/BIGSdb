import socket
from dataclasses import dataclass, field
from types import TracebackType
from typing import List, Tuple, Type, Union

import psycopg

from bioit_mongodb_scripts.util.python_utility_functions import send_email
from .databaseconnection import DatabaseConnection


@dataclass
class GeneDetectionProfilesBatchData:
    """
    This class initializes the lists to store the values that will fill the db fields.
    """
    loci_fields: List[Tuple[Union[int, str], ...]] = field(default_factory=list)
    scheme_members_fields: List[Tuple[Union[str, int], ...]] = field(default_factory=list)
    client_dbase_loci_fields: List[Tuple[Union[str, int], ...]] = field(default_factory=list)
    isolates_loci_fields: List[Tuple[Union[str, int], ...]] = field(default_factory=list)
    sequences_fields: List[Tuple[Union[str, int], ...]] = field(default_factory=list)


class GeneDetectionProfilesBatchInserter:
    """
    This class opens connections to seqdef and isolates DB and performs the insertion of gene detection schemes by batch
    """

    def __init__(self, species: str) -> None:
        """
        open database connections, one to isolates and the other to the seqdef db.
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: None
        """
        self._isolates_db_connection = DatabaseConnection(species, db_type='isolates', autocommit=False)
        self._seqdef_db_connection = DatabaseConnection(species, db_type='seqdef', autocommit=False)

    def insert(self, batch_data: GeneDetectionProfilesBatchData) -> None:
        """
        This method performs the insertion of gene detection scheme elements by batch.
        :param batch_data: GeneDetectionProfilesBatchData
        """
        try:
            self.insert_multiple_loci_seqdef(batch_data.loci_fields)
            self.insert_multiple_scheme_members(self._seqdef_db_connection, batch_data.scheme_members_fields)
            self.insert_multiple_loci_client_db(batch_data.client_dbase_loci_fields)
            self.insert_multiple_loci_isolates(batch_data.isolates_loci_fields)
            self.insert_multiple_scheme_members(self._isolates_db_connection, batch_data.scheme_members_fields)
            self.insert_multiple_sequences(batch_data.sequences_fields)

            self._seqdef_db_connection.connection.commit()
            self._isolates_db_connection.connection.commit()
        except Exception as e:
            self._seqdef_db_connection.connection.rollback()
            self._isolates_db_connection.connection.rollback()
            send_email(
                f'The following error was raised during the insertion of gene detection scheme elements by batch: {e.args[0]}',
                f'GeneDetectionProfilesBatchInserter failed on {socket.gethostname()}')
            raise Exception

    def insert_multiple_loci_seqdef(self, data: list) -> None:
        """
        To insert multiple loci in seqdef.
        :param data: list of values to fill the sql insert statements
        :return: None
        """
        self._seqdef_db_connection.execute_many(
            "INSERT INTO loci (id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", data)

    @staticmethod
    def insert_multiple_scheme_members(connection: psycopg.connection, data: List) -> None:
        """
        To insert multiple scheme_members.
        :param connection: psycopg connection
        :param data: list of values to fill the sql insert statements
        :return: None
        """
        connection.execute_many(
            "INSERT INTO scheme_members (scheme_id, locus, curator, datestamp) VALUES (%s,%s,%s,%s)", data)

    def insert_multiple_loci_client_db(self, data: list) -> None:
        """
        to insert multiple loci in client db
        :param data: list of values to fill the sql insert statements
        :return: None
        """
        self._seqdef_db_connection.execute_many(
            "INSERT INTO client_dbase_loci (client_dbase_id, locus, curator, datestamp) VALUES (%s,%s,%s,%s)", data)

    def insert_multiple_loci_isolates(self, data: list) -> None:
        """
        to insert multiple loci in isolates
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        self._isolates_db_connection.execute_many(
            "INSERT INTO loci (id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, url, isolate_display, main_display, query_field, "
            "analysis, submission_template, curator, date_entered, datestamp) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", data)

    def insert_multiple_sequences(self, data: list) -> None:
        """
        inserts multiple sequences for a given allele and locus
        :param data: list of values to fill the sql insert statement
        :return: None
        """
        self._seqdef_db_connection.execute_many(
            "INSERT INTO sequences (locus, allele_id, sequence, status, sender, curator, date_entered, datestamp) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", data)

    def __enter__(self):
        """
        Enter the runtime context related to the class (interest: connections).
        __enter__/__exit__ methods are used to get the context manager to call the class in a "with" statement
        """
        return self

    def __exit__(self, exc_type: Type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """
        Closes the db connections at the end of the run.
        __enter__/__exit__ are used to get the context manager to call the class in a "with" statement.
        """
        self._isolates_db_connection.close()
        self._seqdef_db_connection.close()
