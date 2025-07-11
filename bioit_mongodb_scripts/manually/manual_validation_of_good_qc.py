import argparse
import logging
import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSubmissions
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data
from bioit_bigsdb_scripts.sample_validation_to_mongo import SampleValidationToMongo

# Configure stdout logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def parse_arguments(specieslist: list[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :specieslist: a list of currently accepted species names.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


class ManualValidationOfGoodQc:
    """
    class to validate the submissions for good qc and to automatically insert them into Mongo and BIGSdb
    """

    def __init__(self, species: str):
        """
        initialize the class
        species: species among the allowed species
        """
        self._species = species

    def get_submission_id_for_pending_goodqc(self) -> list:
        """
        get submission_id for goodqc pending for validation
        :return: list of submission_id
        """
        with TblSubmissions(self._species) as isolates_submissions_psql_tbl:
            list_tuple_sub_id = (isolates_submissions_psql_tbl.get_submission_ids_for_specific_status_and_quality(('pending', 'good')))
            return list(map(lambda x: x[0], list_tuple_sub_id))

    def run(self) -> None:
        """
        this function will run the validation of the submissions until the isolates are inserted into mongo and bigsdb
        :return: None
        """
        submission_id_to_validate = self.get_submission_id_for_pending_goodqc()
        with TblSubmissions(self._species) as isolates_submissions_psql_tbl:
            for sub_id in submission_id_to_validate:
                isolates_submissions_psql_tbl.validate_submission((sub_id,))
                SampleValidationToMongo(self._species, sub_id)
                logger.info(f'process submission id {sub_id}')


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))

    # run main
    ManualValidationOfGoodQc(args.species).run()
