import sys
from builtins import BaseException
from pathlib import Path
from types import TracebackType
from typing import Any, List, Optional, Tuple, Type, Union

import psycopg2
import psycopg2.extensions

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data


class DatabaseConnection:
    """
    Class containing function to open database connections to bigsdb
    """
    def __init__(self, species: str, db_type: str, autocommit: bool = True) -> None:
        """
        Initialises a database connection
        :param species: commonly used bioit species name: either genus or specific like stec
        :param db_type: seqdef or isolates or jobs
        :param autocommit: if True every operation is done in a separate transaction
        :return: None
        """
        self._db_type = db_type
        if self._db_type != 'seqdef' and self._db_type != 'isolates' and self._db_type != 'jobs':
            raise ValueError('no such database type')
        # Read the global config
        bigsdb_config_data = get_bigsdb_config_data()

        database = "bigsdb_jobs" if self._db_type == 'jobs' else f"bigsdb_{species}_{self._db_type}";

        try:
            self._connection: psycopg2.extensions.connection = \
                psycopg2.connect(database=database, user="apache",
                                 password=bigsdb_config_data.get('postgresql_apache_pass'),
                                 host="127.0.0.1", port="")
        except Exception:
            raise RuntimeError(f"Could not connect to {species}'s databases")

        self._connection.autocommit = autocommit
        self._cursor: psycopg2.extensions.cursor = self._connection.cursor()
        self.name = self._cursor.name

    def execute_query(self, query: str, params: Union[Tuple[Union[str, int, Tuple[str]]], List[Union[str, int]], Tuple[str, str, str, str, str]]) \
            -> Optional[List[Optional[Tuple[Any]]]]:
        """
        Executes a sql query using psycopg2 sanitazation
        :param query: sql query to be used
        :param params: parameters to be passed to sqlquery
        :return: None or query results
        """
        self._cursor.execute(query, params)
        # import logging
        # logging.info(self._cursor.query)  # if you ever want to see the filled in query for debugging purposes
        if query.strip().startswith('SELECT'):
            return self._cursor.fetchall()

    def execute(self, query: str) -> Optional[List[Optional[Tuple[Any]]]]:
        """
        Executes a sql query using psycopg2 sanitazation
        :param query: sql query to be used
        :return: None or query results
        """
        self._cursor.execute(query)
        if query.strip().startswith('SELECT'):
            return self._cursor.fetchall()

    def __enter__(self) -> 'DatabaseConnection':
        """
        Returns instance of DatabaseConnection
        :return: DatabaseConnection instance
        """
        return self

    def close(self) -> None:
        """
        Closes the cursor and database connection
        :return: None
        """
        if not self._connection.autocommit:
            self._connection.commit()
        self._cursor.close()
        self._connection.close()

    def __exit__(self, exc_type: Type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
        """
        Closes the cursor and connection automatically upon
        :param exc_type:
        :param exc_val:
        :param exc_tb:
        :return:
        """
        self.close()
