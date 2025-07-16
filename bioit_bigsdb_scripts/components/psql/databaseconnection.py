import sys
from pathlib import Path
from types import TracebackType
from typing import Any, List, Optional, Tuple, Union, Literal, Type

import psycopg

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data


class DatabaseConnection:
    """
    Class containing function to open database connections to BIGSdb. To be used with a context manager, which
    automatically closes the connection and commits or rolls back
    """
    def __init__(self, species: str, db_type: Literal['seqdef', 'isolates', 'jobs'], autocommit: bool = True) -> None:
        """
        Initialises a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param db_type: seqdef or isolates or jobs
        :param autocommit: if True every operation is committed immediately after execution
        :return: None
        """
        self._db_type = db_type
        # Read the global config
        bigsdb_config_data = get_bigsdb_config_data()

        database = "bigsdb_jobs" if self._db_type == 'jobs' else f"bigsdb_{species}_{self._db_type}"

        try:
            self.connection = psycopg.connect(
                dbname=database,
                user="apache",
                password=bigsdb_config_data.get('postgresql_apache_pass'),
                host="127.0.0.1",
                port="",
                autocommit=autocommit
            )
        except Exception:
            raise RuntimeError(f"Could not connect to {species}'s databases")

    def execute_query(self, query: str, params: Union[Tuple[Union[str, int, Tuple[str]]], List[Union[str, int]], Tuple[str, str, float]]) \
            -> Optional[List[Optional[Tuple[Any]]]]:
        """
        Executes a sql query using psycopg sanitization
        :param query: sql query to be used
        :param params: parameters to be passed to sqlquery
        :return: None or query results
        """
        with self.connection.cursor() as cur:  # Not ideal to open a context manager for every single query (would be
            # better if some queries can be grouped.
            cur.execute(query, params)
            # import logging
            # logging.info(cur.query)  # if you ever want to see the filled in query for debugging purposes
            if query.strip().startswith('SELECT'):
                return cur.fetchall()

    def execute_query_client_cursor(self, query: str, params: Union[Tuple[Union[str, int, Tuple[str]]], List[Union[str, int]], Tuple[str, str, float]]) \
            -> Optional[List[Optional[Tuple[Any]]]]:
        """
        Executes a sql query using the ClientCursor which merges the query on the client side and sends the query and
        the parameters merged together to the server.
        :param query: sql query to be used
        :param params: parameters to be passed to sqlquery
        :return: None or query results
        """
        with psycopg.ClientCursor(self.connection) as cur:
            cur.execute(query, params)
            if query.strip().startswith('SELECT'):
                return cur.fetchall()

    def execute(self, query: str) -> Optional[List[Optional[Tuple[Any]]]]:
        """
        Executes a sql query using psycopg sanitization
        :param query: sql query to be used
        :return: None or query results
        """
        with self.connection.cursor() as cur:
            cur.execute(query)
            if query.strip().startswith('SELECT'):
                return cur.fetchall()

    def execute_many(self, query: str, params: list) -> None:
        """
        Executes the same query with a sequence of input data using the psycopg executemany method.
        :param query: Sql query to be used
        :param params: list of sql parameters to be used
        :return: None
        """
        with self.connection.cursor() as cur:
            cur.executemany(query, params)

    def __enter__(self) -> psycopg.connection:
        """
        Returns a psycopg connection to the database.
        :return: psycopg connection
        """
        return self

    def close(self) -> None:
        """
        Closes the cursor and database connection
        :return: None
        """
        if not self.connection.autocommit:
            self.connection.commit()
        self.connection.close()

    def __exit__(self, exc_type: Type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """
        Closes the cursor and connection automatically upon
        :param exc_type:
        :param exc_val:
        :param exc_tb:
        :return:
        """
        self.close()
