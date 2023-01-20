import sys
from pathlib import Path
from typing import Tuple

import psycopg2
import psycopg2.extensions
import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_custom_scripts.components.python_utility_functions import get_bigsdb_config_data

class DatabaseConnection:
    """
    Class containing function to open database connections to bigsdb
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def _connection_and_cursor(species: str, db_type: str) -> Tuple[psycopg2.extensions.connection, psycopg2.extensions.cursor]:
        """
        Returns cursor object for given PSQL databases
        :param species: commonly used bioit species name: either genus or specific like stec
        :param db_type: DTAP: dev, test, acc, or prod
        :return: cursor object that can be used to interact: CRUD
        """
        # Read the global config
        bigsdb_config_data = get_bigsdb_config_data()

        con = psycopg2.connect(database=f"bigsdb_{species}_{db_type}", user="apache", password=bigsdb_config_data.get('postgresql_apache_pass'),
                               host="127.0.0.1", port="")
        con.autocommit = True
        cur = con.cursor()
        return con, cur

    def connect_to_dbs_and_create_cursors(self, species: str) \
            -> Tuple[Tuple[psycopg2.extensions.connection, psycopg2.extensions.cursor], Tuple[psycopg2.extensions.connection, psycopg2.extensions.cursor]]:
        """
        Connects to the species specific databases
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: tuples of opened connections and cursors to isolate and seqdef db (objects)
        """
        try:
            return self._connection_and_cursor(species, 'isolates'), self._connection_and_cursor(species, 'seqdef')
        except Exception:
            raise RuntimeError(f"Could not connect to {species}'s databases")

    def close_connections(self, con_isolates: psycopg2.extensions.connection, con_seqdef: psycopg2.extensions.connection) -> None:
        """
        closes the connections
        :param con_isolates: isolates database connection instance
        :param con_seqdef:
        :return: None
        """
        con_isolates.close()
        con_seqdef.close()
