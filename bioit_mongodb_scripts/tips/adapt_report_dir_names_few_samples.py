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

    isolates_in_mongo = isolates_collection.distinct('_id')
    # isolates_badid_in_mongo = isolates_collection.distinct("_id", { "orig_isolates_id": { "$exists": False} }) # si on avait voulu ne reprendre que ceux qui n'ont pas été renomés
    renamed_in_mongo = Mongoquerying.query_list_of_all_distinct_values(isolates_collection,
                                                                       'orig_isolates_id')  # et ça pour avoir leur id avant d'être renomés

    isolates_in_mongo_badqc = isolates_badqc_collection.distinct("_id")

    all_mongo_id = isolates_in_mongo + isolates_in_mongo_badqc

    reports_folder = '/reports/neisseria/'

    tobedone = ['S17BD01804','S23BD00192','S23BD00236','S23BD04233','S23BD04251']

    date_to_give='2023-06-27'
    p = Path(reports_folder)
    tobeadapt = []
    tobeadaptfold = []
    inerror2 = []
    list_of_subfolder = [x for x in p.iterdir() if x.is_dir()]
    for i in list_of_subfolder:
        report = i.stem
        mongoid = re.sub("_S[0-9]*_L[0-9]*", "", report)
        if mongoid in tobedone:
            try:
                startpoint = report.index('_S')
                new_fold_name = report[:report.index('_S')] + "_" + str(date_to_give)
                new_path = Path(i.parent, new_fold_name)
                new_path_for_mongo = str(new_path)
                tobeadaptfold.append(new_path_for_mongo)

                mongoquering.duplicate_Mongofield_under_newname(opened_collection=isolates_collection,
                                                                mongo_id=mongoid, field_to_copy='report_directory',
                                                                new_field_name='orig_report_directory')
                isolates_collection.update_one({"_id": mongoid}, {"$set": {"report_directory": new_path_for_mongo}})
                shutil.move(i, new_path)

            except (ValueError,TypeError):
                print("_S n'a pas été vu")
                inerror2.append(report)

    print('It is done')
    print('in error:')
    print(inerror2)