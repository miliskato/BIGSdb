import psycopg2
import yaml
import os
import sys

PYTHONPATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(PYTHONPATH))

from bioit_custom_scripts.config import BIGSDB_CONFIG

class DatabaseConnection:
    """
    Class containing function to open database connections to bigsdb
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def _connection(species: str, db_type: str) -> object:
        """
        Returns cursor object for given PSQL databases
        :param species: commonly used bioit species name: either genus or specific like stec
        :param db_type: DTAP: dev, test, acc, or prod
        :return: cursor object that can be used to interact: CRUD
        """
        # Read the global config
        with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
            config_data = yaml.safe_load(handle)

        con = psycopg2.connect(database=f"bigsdb_{species}_{db_type}", user="apache", password=config_data.get('postgresql_apache_pass'),
                               host="127.0.0.1", port="")
        con.autocommit = True
        cur = con.cursor()
        return cur

    def open_database_connections(self, species: str) -> object:
        """
        Connects to the species specific databases
        :param species:
        :return: opened connection to isolate and seqdef db (objects)
        """
        try:
            return self._connection(species, 'isolates'), self._connection(species, 'seqdef')
        except Exception:
            raise RuntimeError(f"Could not connect to {species}'s databases")
