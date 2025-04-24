# to put in bioit_bigsdb_scripts
import argparse
import logging
import sys
from pathlib import Path
from typing import List

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))


from bioit_bigsdb_scripts.components.psql import TblIsolates, TblMappingTable
from bioit_mongodb_scripts.model.json_model import MongoRecordDict
from bioit_mongodb_scripts.util.alerts_to_bigs import AlertsToBigs
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


def isolate_and_cgst(document: MongoRecordDict, isolate_id: str):
    """
    Function to append isolate_id, cgST, and date_of_isolation to a list that will be used to re-compute BIGSdb alerts
    :param document: Mongo record from isolate collection
    :param isolate_id: isolate id (as found in BIGSdb)
    """
    return {'isolate_name': isolate_id, 'cgST': document['results'].get('cgST'), 'isolation_date': document['technical_metadata']['data']['IsolationDate']}


if __name__ == '__main__':

    # Configure stdout logging
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)
    mongo_config_provider = MongoConfigProvider()

    args = parse_arguments(mongo_config_provider.get_all_species())
    mongo_init = MongoInitialisation(args.species, mongo_config_provider.get_azure_connection_string(args.species), mongo_config_provider.dtap)
    isolates_collection, _, _, _ = mongo_init.initialise_collections()
    naive_clustering_distance_matrix_file = Path(
        mongo_config_data['naive_clustering_distance_matrix_file'].replace('species', args.species).replace('dtap', mongo_config_data.get('dtap')))

    new_version_isolates = []
    new_isolates = []

    with TblIsolates(args.species) as isolates_psql_tbl:
        yo = isolates_psql_tbl.listing_isolates()

    for item in yo:
        with TblMappingTable(args.species) as mapping_psql_tbl:
            pseudo_id = mapping_psql_tbl.select_pseudo_id_for_isolate(item)[0][0]

        doc = MongoRecordDict(isolates_collection.find_one({'_id': pseudo_id}))
        new_isolates.append(isolate_and_cgst(doc, item[0]))

    AlertsToBigs(new_isolates, new_version_isolates, args.species, 2, naive_clustering_distance_matrix_file)
