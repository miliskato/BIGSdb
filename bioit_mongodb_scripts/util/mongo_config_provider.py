import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import MONGO_CONFIG


def get_mongodb_config_data() -> Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]:
    """
    Reads the global bigsdb config
    :return:
    """
    with Path(MONGO_CONFIG).open('r') as handle:
        mongo_config_data = yaml.safe_load(handle)
    return mongo_config_data


class MongoConfigProvider:
    """
    Class to facilitate access to the different parts of the global mongodb config.
    """

    def __init__(self, alternate_dtap: Optional[Literal['dev', 'test', 'acc', 'prod']] = None):
        self._mongo_global_config = get_mongodb_config_data()
        self.dtap = self._mongo_global_config['dtap'] if alternate_dtap is None else str(alternate_dtap)
        self.__password = self._mongo_global_config['MONGO_DB_PASSWORD']
        self.upload_path = 'upload/' + f"{(alternate_dtap + '/') if alternate_dtap else ''}"

    def _get_user(self, species: str):
        return f'User{species}_{self.dtap}'

    def get_local_connection_string(self, species: str) -> str:
        """
        get local connection string to mongo
        :return: connection string
        """
        return f'mongodb://{self._get_user(species)}:{self.__password}@bioit-mongo-d01.sciensano.be:27017,bioit-mongo-d02.sciensano.be:27017,bioit-mongo-d03.sciensano.be:27017/?authSource={species}_{self.dtap}&replicaSet=bioit-HERA'

    def get_azure_connection_string(self, species: str) -> str:
        """
        get azure connection string to mongo
        :return: connection string
        """
        return f'mongodb+srv://{self._get_user(species)}:{self.__password}@mongodb-atlas-devtest-pl-0.fgpmn.mongodb.net/?retryWrites=true&w=majority'

    def get_alternate_connection_string(self) -> str:
        """
        get alternate connection string to mongo
        :return: connection string
        """
        return self._mongo_global_config['CONNECTION_STRING_ALTERNATE']

    def is_viral(self) -> bool:
        """
        Check if the current species is viral
        :param species: species to evaluate
        :return: True if species is viral
        """
        return self.species in self._mongo_global_config['viral_species']

    def get_asb_connection_string(self) -> str:
        return self._mongo_global_config['CONNECTION_STRING_ASB']

    def get_all_species(self) -> List[str]:
        return self._mongo_global_config['species']

    def get_schemes_sequence_typing(self) -> List[str]:
        return self._mongo_global_config['schemes_sequence_typing']

    def get_naive_clustering_distance_matrix_file(self, species: str) -> str:
        naive_clustering_distance_matrix_path = self._mongo_global_config['naive_clustering_distance_matrix_file'].replace('species', species).replace('dtap', self.dtap)
        return naive_clustering_distance_matrix_path

    def get_temp_dir(self) -> str:
        return self._mongo_global_config['temp_dir']

    def get_azure_reportsapi_ip(self):
        return self._mongo_global_config['azure_reportsapi_ip']

    def get_mongo_collections(self) -> List[str]:
        return self._mongo_global_config['collections']
