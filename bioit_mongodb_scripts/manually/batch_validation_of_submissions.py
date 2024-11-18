import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import List

from bioit_bigsdb_scripts.components.psql import TblSubmissions
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_bigsdb_scripts.sample_validation_to_mongo import SampleValidationToMongo


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', type=str, choices=specieslist)
    argument_parser.add_argument('--accept_all', required=False, type=str, choices=['yes', 'no'])
    return argument_parser.parse_args()

class BatchValidationToMongo:
    """
    This class handles validation/insertion in mongoDB of badqc already pushed in BIGSdb submission table.
    """
    def __init__(self, species: str, accept_all: str = 'no') -> None :
        """
        Initialises the class and runs the main function
        :param species: commonly used bioit species name.
        :param accept_all: set to True to accept all badqc pending for submission in BIGSdb. If False, only badqc
        submissions with current values for status and outcome equal to "closed" and "good" will be processed
        :return: None
        """
        self.species = species
        self.accept_all = accept_all

        try:
            self.validate_pending_submission_for_badqc()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name} fail on host {socket.gethostname()}")
            raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")

    def validate_pending_submission_for_badqc(self):
        with TblSubmissions(species=self.species) as isolates_submissions_psql_tbl:
            if self.accept_all == 'yes':
                isolates_submissions_psql_tbl.validate_pending_badqc()
            submission_ids=list(isolates_submissions_psql_tbl.get_submission_id_for_validated_badqc())

        for sub_id in submission_ids:
            SampleValidationToMongo(self.species, sub_id = int(sub_id[0]))


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))

    # run main
    BatchValidationToMongo(args.species, accept_all = (args.accept_all if args.accept_all else None))
