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
    mongoinit = MongoInitialisation(args.species, mongo_config_data=mongo_config_data)

    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
    headers_collection = mongoinit.initialise_headers_collection()

    isolates_in_mongo_badqc = isolates_badqc_collection.distinct('_id')
    isolates_in_mongo_resequencing = isolates_resequencing_collection.distinct('_id')

    isolates_renamed_mongo_badqc = ["RRS16BD06804","S19BD08137bis","S16BD03995R"]

    not_renamed_in_mongo = isolates_in_mongo_badqc + isolates_in_mongo_resequencing

    reports_folder = '/reports/neisseria/'

    today = date.today()
    p = Path(reports_folder)
    list_of_subfolder = [x for x in p.iterdir() if x.is_dir()]

    subfolder_of_interest = []
    already_adapt_reports = []
    for i in list_of_subfolder:
        reports_name = i.stem
        if '_2023-06-27' in reports_name:
            nameok = reports_name.replace('_2023-06-14', '')
            already_adapt_reports.append(nameok)

        else:
            subfolder_of_interest.append(i)

    path_adapted= []
    not_found_isolates = []
    for i in isolates_in_mongo_badqc:
        mongo_query = isolates_badqc_collection.find_one({"_id": i}, {"report_directory": 1})
        report_to_adapt = mongo_query["report_directory"]
        str_to_find=str( "/" + Path(report_to_adapt).stem )
        new_report_path = report_to_adapt[:report_to_adapt.index(str_to_find)] + "/" + str(i) + "_" + str(today)
        if (Path(report_to_adapt).is_dir()) and (report_to_adapt != new_report_path):
            new_path=Path(new_report_path)
            mongoquering.duplicate_Mongofield_under_newname(opened_collection=isolates_badqc_collection,
                                                            mongo_id=i, field_to_copy='report_directory',
                                                            new_field_name='orig_report_directory')
            isolates_badqc_collection.update_one({"_id": i}, {"$set": {"report_directory": new_report_path}})
            shutil.move(Path(report_to_adapt), new_path)
            path_adapted.append(new_report_path)

    for i in isolates_in_mongo_resequencing:
        mongo_query = isolates_resequencing_collection.find_one({"_id": i}, {"report_directory": 1})
        report_to_adapt = mongo_query["report_directory"]
        str_to_find = str("/" + Path(report_to_adapt).stem)
        new_report_path = report_to_adapt[:report_to_adapt.index(str_to_find)] + "/" + str(i) + "_" + str(today)
        if (Path(report_to_adapt).is_dir()) and (report_to_adapt != new_report_path):
            new_path=Path(new_report_path)
            mongoquering.duplicate_Mongofield_under_newname(opened_collection=isolates_resequencing_collection,
                                                            mongo_id=i, field_to_copy='report_directory',
                                                            new_field_name='orig_report_directory')
            isolates_resequencing_collection.update_one({"_id": i}, {"$set": {"report_directory": new_report_path}})
            shutil.move(Path(report_to_adapt), new_path)
            path_adapted.append(new_report_path)

