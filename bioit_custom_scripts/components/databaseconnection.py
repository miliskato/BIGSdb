import psycopg2


class DatabaseConnection:
    """
    Class containing defintion to open database connection
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
        con = psycopg2.connect(database=f"bigsdb_{species}_{db_type}", user="apache", password="remote",
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
