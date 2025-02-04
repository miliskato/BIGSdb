#!/usr/bin/env python
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Union

# import dnspython
# somehow this package is a requirement without actually needing to be imported, probably imported in pymongo

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


def parse_arguments(species_list: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    !! If new arguments are added, Also add arguments/variables to main function/class!!
    :param species_list: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=species_list)
    parser.add_argument("--technical_id", required=True, type=str)
    parser.add_argument("--rejection_reason", required=True, type=str, choices=['abc', 'def'])
    parser.add_argument('--alternate_dtap', choices=['dev', 'test', 'acc', 'prod'], help=argparse.SUPPRESS)
    return parser.parse_args()


class InsertFailedSampleAsRejectedManually:
    """
    Class containing only an __init__ function which will insert an isolate into the rejected isolates MongoDB Azure
    collection.
    """
    def __init__(self, technical_id: str, species: str, rejection_reason: Literal['abc', 'def'],
                 alternate_dtap: Union[str, None] = None) -> None:
        """
        Insert an isolate into the rejected isolates MongoDB Azure collection with a given rejection reason.
        :param technical_id: sample id/ isolates id
        :param species: commonly used bioit species name: either genus or specific like stec
        :param rejection_reason: The reason why the sample failed/has to be rejected.
        :param alternate_dtap: alternative dtap than what is in the config file
        """
        mongoinit = MongoInitialisation(species,
                                        selected_connection_string='CONNECTION_STRING_AZURE',
                                        alternate_dtap=alternate_dtap,
                                        mongo_config_data=get_mongodb_config_data())

        isolates_rejected_coreqc_collection = mongoinit.initialise_isolates_rejected_coreqc_collection()
        isolates_rejected_coreqc_collection.insert_one({
            "_id": technical_id,
            "rejection_reasons": [rejection_reason],
            "creation_date": datetime.now(timezone.utc),
            "insertion_type": 'manual'})


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    InsertFailedSampleAsRejectedManually(args.technical_id,
                                         args.species,
                                         args.rejection_reason,
                                         args.alternate_dtap)
