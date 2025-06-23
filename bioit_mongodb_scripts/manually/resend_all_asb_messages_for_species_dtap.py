import argparse
import sys
from pathlib import Path
from typing import List

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util_azure.azure_service_bus import AzureServiceBus
from bioit_mongodb_scripts.util_azure.azure_service_bus_message import AzureServiceBusMessage


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    !! If new arguments are added, Also add arguments/variables to main function/class!!
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str,
                        choices=specieslist)
    parser.add_argument('--alternate_dtap', choices=['dev', 'test', 'acc', 'prod'])
    return parser.parse_args()


if __name__ == '__main__':

    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    mongoinit = MongoInitialisation(args.species,
                                    selected_connection_string='CONNECTION_STRING_AZURE',
                                    alternate_dtap=args.alternate_dtap,
                                    mongo_config_data=mongo_config_data)
    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
        isolates_resequencing_collection, isolates_goodqc_collection = mongoinit.initialise_collections()

    rejected_isolates_collection = mongoinit.initialise_isolates_rejected_coreqc_collection()

    asb_instance = AzureServiceBus(mongo_config_data, args.species, args.alternate_dtap)
    for collection in [isolates_collection, old_isolateresults_collection, isolates_badqc_collection,
                       isolates_resequencing_collection, isolates_goodqc_collection, rejected_isolates_collection]:
        sample_ids = [x['_id'] for x in collection.find({}, {'_id': 1}) if isinstance(x['_id'], str)]
        for sample_id in sample_ids:
            asb_instance.send_message_to_queue(AzureServiceBusMessage(sample_id, collection.name))
