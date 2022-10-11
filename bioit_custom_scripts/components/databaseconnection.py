import psycopg2

class Database_connection:
    """
    Class containing defintion to open database connection
    """

    def __init__(self):
        pass

    def open_database_connections(self, species):
        """
        Connects to the species specific databases
        :param species:
        :return: opened connection to isolate and seqdef db (objects)
        """
        def connection(species, db_type):
            con = psycopg2.connect(database=f"bigsdb_{species}_{db_type}", user="apache", password="remote",
                                    host="127.0.0.1", port="")
            con.autocommit = True
            cur = con.cursor()
            return cur
        try:
            return connection(species, 'isolates'), connection(species, 'seqdef')
        except:
            raise RuntimeError(f"Could not connect to {species}'s databases")

