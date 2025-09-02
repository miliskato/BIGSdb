
from .mongo_config_provider import MongoConfigProvider
from .mongo_initialisation import MongoInitialisation


def get_pseudo_id(species: str, isolate_name: str) -> str:
    """Return the corresponding pseudo-id from mongo mapping collection
    :param species: species name
    :param isolate_name: isolate name
    :return: pseudo-id
    """
    mongo_config_provider = MongoConfigProvider()
    mongo_init_local = MongoInitialisation(species, mongo_config_provider.get_local_connection_string(species), mongo_config_provider.dtap)
    mapping_collection = mongo_init_local.initialise_mapping_table_collection()
    pseudo_id = mapping_collection.find_one({"_id": isolate_name})['pseudo_id']
    if pseudo_id is None:
        raise Exception(f"pseudo_id for {isolate_name} is not found")
    return str(pseudo_id)
