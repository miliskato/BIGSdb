import yaml
import argparse
from pathlib import Path
import os
import sys

PYTHONPATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.util.new_threshold_clustering import NewThresholdClustering
from MongoDB.util.mongo_initialisation import MongoInitialisation
from MongoDB.config import MONGO_CONFIG

def parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    parser.add_argument("--new_cl_thresh", required=True, type=str,  help='list writen without spaces between brackets')
    parser.add_argument("--cl_config", required=True, type=Path)
    return parser.parse_args()



if __name__ == '__main__':

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse arguments
    args = parse_arguments(config_data['species'])
    # Open collections
    mongoinit = MongoInitialisation()
    st_collection, cluster_membership_collection = \
        mongoinit.initialise_clustering_collections(config_data, args.species)

    new_threshold_clustering = NewThresholdClustering(st_collection, cluster_membership_collection, args.cl_config,
                                                      eval(args.new_cl_thresh), args.species)
    new_threshold_clustering.create_new_threshold_and_compute_clustering()