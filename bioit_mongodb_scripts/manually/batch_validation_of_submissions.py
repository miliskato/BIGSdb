import logging
from typing import List

from bioit_bigsdb_scripts.components.psql import TblSubmissions
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', type=str, choices=specieslist)
    argument_parser.add_argument('--accept_all', required=False, type=bool, default=False)
    return argument_parser.parse_args()

class BatchValidationToMongo:
    """
    This class handles validation/insertion in mongoDB of badqc already pushed in BIGSdb submission table.
    """
    def __init__(self, species: str, accept_all: bool) -> None :
        """
        Initialises the class and runs the main function
        :param species: commonly used bioit species name.
        :param accept_all: set to True to accept all isolates pending for submission.
        :return: None
        """
        #self.species = species
        #self.accept_all = accept_all

    with TblSubmissions(species) as isolates_submissions_psql_tbl:
        if accept_all:
            isolates_submissions_psql_tbl.validate_pending_badqc()




if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))
    species = re.sub('bigsdb_|_isolates', '', args.db) if args.db else args.species

    # run main
    BatchValidationToMongo(species, args.accept_all)
