import argparse
import logging
import sys
import re
import shutil
from pathlib import Path
from datetime import date

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying


def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    return parser.parse_args()


def extend_folder_name(folderlist: list, extensionstr: str) -> None:
    """
    Extension of folder/folders which are listed by a definite str
    :param folderlist: list of path to the target folder
    :param extensionstr: strin to add at the end of the folder name
    """
    for i in folderlist:
        target = i.as_posix() + str
        i.rename(target)


if __name__ == '__main__':
    """
    This script is used to regenerate html static report for sampleID which are already on MongoDB
    """
    # Parse config
    mongo_config_data = get_mongodb_config_data()
    mongoquering = Mongoquerying()
    # Parse arguments
    args = _parse_arguments(list(mongo_config_data['species']))
    # Configure logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Open collections
    mongoinit = MongoInitialisation(args.species, mongo_config_data=mongo_config_data, selected_connection_string='CONNECTION_STRING_AZURE')

    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
    headers_collection = mongoinit.initialise_headers_collection()

    isolates_in_mongo = isolates_collection.distinct('_id')
    isolates_in_mongo_badqc = isolates_badqc_collection.distinct('_id')
    isolates_in_mongo_resequencing = isolates_resequencing_collection.distinct('_id')

    list_to_rename = ['S23BD00865']

    equivalence = {}
    not_found = []
    for i in list_to_rename:
        try:
            mongo_query = isolates_collection.find_one({"_id": i}, {"report_directory": 1,"orig_report_directory": 1})
            report = mongo_query["report_directory"]
            original_report = mongo_query["orig_report_directory"]
            equivalence[i] = original_report
        except (ValueError,TypeError):
                not_found.append(i)


    print(equivalence)
    print(not_found)


