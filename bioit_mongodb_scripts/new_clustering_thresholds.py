import argparse
import sys
from pathlib import Path
from typing import List

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.new_threshold_clustering import NewThresholdClustering
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    parser.add_argument("--new_cl_thresh", required=True, type=int, nargs='+',
                        help='Arguments passed as space separated values: e.g. --new_cl_thresh 10 15')
    parser.add_argument("--cl_config", required=True, type=Path)
    return parser.parse_args()


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # Open collections
    mongoinit = MongoInitialisation(args.species, mongo_config_data=mongo_config_data)
    st_collection, cluster_membership_collection, cluster_merging_collection = \
        mongoinit.initialise_clustering_collections()
    headers_collection = mongoinit.initialise_headers_collection()

    # Run main
    new_threshold_clustering = NewThresholdClustering(st_collection, cluster_membership_collection, headers_collection,
                                                      cluster_merging_collection, args.cl_config,
                                                      set(args.new_cl_thresh), args.species)
    new_threshold_clustering.create_new_threshold_and_compute_clustering()
