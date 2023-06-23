import argparse
import logging
import sys
from pathlib import Path
from datetime import date

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.htmlreport_generation import HtmlreportGeneration

from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data

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




if __name__ == '__main__':
    """
    This script is used to regenerate html static report for sampleID which are already on MongoDB
    """
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = _parse_arguments(list(mongo_config_data['species']))

    # Configure logging
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Open collections
    mongoinit = MongoInitialisation(args.species, mongo_config_data=mongo_config_data)

    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
    headers_collection = mongoinit.initialise_headers_collection()

    # isolates_collection.drop()
    # old_isolateresults_collection.drop()
    samplesforhtml=Mongoquerying.query_list_of_all_distinct_values(isolates_collection, '_id')

    with open('/home/angori/ASGsamples_cleanid.txt','r') as file:
        nottobedone = []
        for line in file:
            line =line.strip()
            nottobedone.append(line)

    res = [i for i in samplesforhtml if i not in nottobedone]

    today = date.today()
    day_reanalyse = today.strftime("%Y-%m-%d")
    type(day_reanalyse)

    for sample in res:
        enddir=fr"/scratch/temp/{sample}_2023-06-14"
        if not Path(enddir).is_dir():
            #HtmlreportGeneration(args.species, sample, analysis_date=day_reanalyse)
            HtmlreportGeneration(args.species, sample, analysis_date='2023-06-14')
