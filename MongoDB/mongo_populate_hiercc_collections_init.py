from pymongo import MongoClient
# import dnspython
import yaml
import argparse
from pathlib import Path
import logging
from datetime import datetime
import sys

from util.mongo_results import Mongoresults
from util.mongo_querying import Mongoquerying
from util.mongo_initialisation import Mongoinitialisation
from util.mongo_hiercc_clustering import MongoHierCCClustering
from config import MONGO_CONFIG


if __name__ == '__main__':
    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Open collections
    mongoinit = Mongoinitialisation()
    #listeria collection
    st_collection, hiercc_results_collection = mongoinit._initialise_hiercc_collections(config_data, 'listeria')

    mongoquerying = Mongoquerying()


