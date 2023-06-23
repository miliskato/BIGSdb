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
        target=i.as_posix() + str
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

    isolates_in_mongo=isolates_collection.distinct('_id')
    #isolates_badid_in_mongo = isolates_collection.distinct("_id", { "orig_isolates_id": { "$exists": False} }) # si on avait voulu ne reprendre que ceux qui n'ont pas été renomés
    #renamed_in_mongo=Mongoquerying.query_list_of_all_distinct_values(isolates_collection, 'orig_isolates_id') # et ça pour avoir leur id avant d'être renomés

    isolates_in_mongo_badqc=isolates_badqc_collection.distinct("_id")

    all_mongo_id = isolates_in_mongo + isolates_in_mongo_badqc

    p = Path('/scratch/temp/')
    list_of_subfolder = [x for x in p.iterdir() if x.is_dir()]

    regenerated_reports = []
    for i in list_of_subfolder:
        reports_name = i.stem
        if '_2023-06-14' in reports_name:
            nameok = reports_name.replace('_2023-06-14', '')
            regenerated_reports.append(nameok)

    regenerated_in_Mongo = [i for i in regenerated_reports if i in all_mongo_id]
    if len(regenerated_in_Mongo) != len(regenerated_reports):
        sys.exit("Some regenarated reports not found in Mongo _id")

    p2 = Path('/reports/neisseria/')
    list_of_subfolder2 = [x for x in p2.iterdir() if x.is_dir()]
    new_reports = []
    for i in list_of_subfolder2:
        reports_name = i.stem
        nameok = re.sub("_S[0-9]*_L[0-9]*", "", reports_name)
        new_reports.append(nameok)


    with open('/home/angori/ASGsamples_cleanid.txt','r') as file:
        tobedone = []
        for line in file:
            line =line.strip()
            tobedone.append(line)

    new_reports = [x for x in new_reports if x not in regenerated_reports] # remove those which are already processed above
    new_reports_expect = [x for x in new_reports if x in tobedone] #check how many are found
    if len(new_reports_expect) != len(tobedone):
        missing_one= [x for x in tobedone if x not in new_reports_expect]
        for item in missing_one:
            print(item + ' is not found!')
    other_reports = [x for x in new_reports if x not in tobedone]
    reports_from_bad_qc = [ x for x in other_reports if x in isolates_badqc_collection.distinct('_id') ]
    reports_from_reseq = [x for x in other_reports if x in isolates_resequencing_collection.distinct('_id')]
    reports_from_old = [x for x in other_reports if x in old_isolateresults_collection.distinct('_id')]
    len_reports_from_bad_or_reseq=(len(reports_from_reseq)+len(reports_from_bad_qc)+len(reports_from_old))
    if len(other_reports) != (len(reports_from_reseq)+len(reports_from_bad_qc)):
        print(str(len(other_reports))+" expected and found "+ str(len_reports_from_bad_or_reseq))



    p = Path('/scratch/temp/')
    list_of_subfolder = [x for x in p.iterdir() if x.is_dir()]
    today = date.today()
    for i in list_of_subfolder:
        report = i.stem

        try:
            report.index("2023")
            report[:report.index("2023")]
            new_fold_name=report[:report.index("2023")]+str(today)
            new_path=Path(i.parent, new_fold_name)
            new_path_for_mongo=str(new_path)

            mongoid = report.replace('_2023-06-14', '')
            #i.rename(new_path)

            #mongoquering.duplicate_Mongofield_under_newname(opened_collection=isolates_collection,
            #                                                 mongo_id=mongoid, field_to_copy='report_directory',
            #                                                 new_field_name='orig_report_directory')
            #isolates_collection.update_one({"_id": mongoid}, {"$set": {"report_directory": new_path_for_mongo}})

        except ValueError as e:
            print(str.format("Can find 2023 extension"))

    p = Path('/reports/neisseria/')
    tobeadapt=[]
    tobeadaptfold=[]
    list_of_subfolder = [x for x in p.iterdir() if x.is_dir()]
    for i in list_of_subfolder:
        report = i.stem
        mongoid = re.sub("_S[0-9]*_L[0-9]*", "", report)
        if mongoid in tobedone:
            try:
                startpoint=report.index('_S')
                new_fold_name = report[:report.index('_S')] + "_" + str(today)
                new_path = Path(i.parent, new_fold_name)
                new_path_for_mongo = str(new_path)
                tobeadaptfold.append(new_path_for_mongo)
                # i.rename(new_path)

                # mongoquering.duplicate_Mongofield_under_newname(opened_collection=isolates_collection,
                #                                                 mongo_id=mongoid, field_to_copy='report_directory',
                #                                                 new_field_name='orig_report_directory')
                # isolates_collection.update_one({"_id": mongoid}, {"$set": {"report_directory": new_path_for_mongo}})
            except (ParserError, ValueError):
                print("_S n'a pas été vu")

    print('It is finally done')







