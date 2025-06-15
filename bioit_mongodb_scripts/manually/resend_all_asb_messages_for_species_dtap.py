import argparse
import sys
from pathlib import Path
from typing import List

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_message import AzureServiceBusMessage


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,  choices=MongoConfigProvider.get_all_species())
    parser.add_argument('--alternate_dtap', choices=['dev', 'test', 'acc', 'prod'])
    return parser.parse_args()


if __name__ == '__main__':

    args = parse_arguments()
    mongo_config_data = MongoConfigProvider(args.alternate_dtap)
    mongoinit = MongoInitialisation(args.species, mongo_config_data.get_azure_connection_string(args.species), mongo_config_data.dtap)
    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
        isolates_resequencing_collection, isolates_goodqc_collection = mongoinit.initialise_collections()

    rejected_isolates_collection = mongoinit.initialise_isolates_rejected_coreqc_collection()

    asb_instance = AzureServiceBus(mongo_config_data, args.species)
    for collection in [isolates_collection, old_isolateresults_collection, isolates_badqc_collection,
                       isolates_resequencing_collection, isolates_goodqc_collection, rejected_isolates_collection]:
        sample_ids = [x['_id'] for x in collection.find({}, {'_id': 1}) if isinstance(x['_id'], str)]
        for sample_id in sample_ids:
            asb_instance.send_message_to_queue(AzureServiceBusMessage(sample_id, collection.name))
