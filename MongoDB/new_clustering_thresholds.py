import yaml
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
import argparse
from MongoDB.util.new_threshold_clustering import NewThresholdClustering
from pathlib import Path




def parse_arguments(specieslist) -> argparse.Namespace:
    """
    Parses the command line arguments.
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
    mongoinit = Mongoinitialisation()
    st_collection, cluster_membership_collection = \
        mongoinit.initialise_clustering_collections(config_data, args.species)

    new_threshold_clustering = NewThresholdClustering(st_collection, cluster_membership_collection, args.cl_config,
                                                      eval(args.new_cl_thresh), args.species)
    new_threshold_clustering.create_new_threshold_and_compute_clustering()