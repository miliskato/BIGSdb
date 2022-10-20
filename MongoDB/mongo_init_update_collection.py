import yaml
import logging
import sys
from pathlib import Path
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
import sys, gzip, logging, click
import datetime
from pymongo.write_concern import WriteConcern


if __name__ == '__main__':
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    #species = ['listeria', 'mycobacterium', 'neisseria', 'salmonella', 'stec']
    species = ['listeria_test']
    # Open collections
    mongoinit = Mongoinitialisation()
    mongoquerying = Mongoquerying()
    for sp in species:
        update_collection = mongoinit.initialise_update_collection(config_data, sp)
        update_collection.with_options(write_concern=WriteConcern(w="majority")).insert_one({
            'metadata': 'last_update',
            'last_update_date': datetime.datetime.utcnow()
        })
        logging.info(f"Initialization of the update collection from {sp} is completed!")