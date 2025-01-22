import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import List

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

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
    argument_parser.add_argument('--accept_all', required=False, action='store_true')
    return argument_parser.parse_args()


class BatchValidationToMongo:
    """
    This class handles validation/insertion in mongoDB of badqcs already pushed in BIGSdb submissions table.
    """

    def __init__(self, species: str, accept_all: bool) -> None:
        """
        Initialises the class and runs the main function
        :param species: commonly used bioit species name.
        :param accept_all: yes/no: if "yes", all badqcs still pending for validation in BIGSdb will be accepted.
        :return: None
        """
        self._species = species
        self._accept_all = accept_all

        try:
            self._validate_pending_submission_for_badqc()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name} fail on host {socket.gethostname()}")
            raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")

    def _validate_pending_submission_for_badqc(self) -> None:
        """
        Method to validate either all the badqc pending for validation in BIGSdb submission table, or only those
        with status and outcome already set to "good" and "closed" by another process.
        :return: None
        """
        with TblSubmissions(species=self._species) as isolates_submissions_psql_tbl:
            if self._accept_all:
                isolates_submissions_psql_tbl.validate_pending_badqcs()
            submission_ids = list(isolates_submissions_psql_tbl.get_submission_ids_for_validated_badqcs())

        for sub_id in submission_ids:
            SampleValidationToMongo(self._species, sub_id=int(sub_id[0]))


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.ERROR, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))

    # run main
    BatchValidationToMongo(args.species, args.accept_all)
