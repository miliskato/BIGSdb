# Usage : python trigger_singlelinkageclustering.py neisseria 5 10
import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data

if __name__ == '__main__':

    # Parse config
    mongo_config_data = get_mongodb_config_data()

    from bioit_mongodb_scripts.util.distance_and_cluster_computer import DistanceAndClusterComputer
    distance_cluster = DistanceAndClusterComputer(sys.argv[1], mongo_config_data)

    threshold_list = []
    n = len(sys.argv)

    for i in range(2, n):
        threshold_list.append(int(sys.argv[i]))

    distance_cluster.compute_hamming_distances('full')
    distance_cluster.init_clustering_and_cluster_membership(set(threshold_list))
