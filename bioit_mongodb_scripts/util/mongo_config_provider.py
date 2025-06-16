import socket
import sys
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

import yaml

from bioit_bigsdb_scripts.utils.literal_helper import validate_literal

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


DtapValues = Literal['dev', 'test', 'acc', 'prod']
DtapValue = Union[str, DtapValues]  # workaround to avoid pycharm warnings


class MongoConfigProvider:
    """
    Class to facilitate access to the different parts of the global mongodb config.
    """

    def __init__(self, alternate_dtap: Optional[DtapValue] = None):
        validate_literal(alternate_dtap, DtapValues)
        self._mongo_global_config = get_mongodb_config_data()
        self.dtap = self._mongo_global_config['dtap'] if alternate_dtap is None else str(alternate_dtap)
        self.__password = self._mongo_global_config['MONGO_DB_PASSWORD']
        self.upload_path = 'upload/' + f"{(alternate_dtap + '/') if alternate_dtap else ''}"

    def _get_user(self, species: str):
        return f'{species}User_{self.dtap}'

    def _get_dtap_extension(self) -> str:
        if self.dtap in ['dev', 'test']:
            return 'devtest'
        return 'accprod'

    def _get_domain_for_dtap(self) -> str:
        if self.dtap in ['dev', 'test']:
            return 'darwinproject.be'
        return 'sciensano.be'

    def get_local_connection_string(self, species: str) -> str:
        """
        get local connection string to mongo
        :return: connection string
        """
        dtap_domain = self._get_domain_for_dtap()
        if self.host_is_an_nrc_platform(species):
            return f'mongodb://{self._get_user(species)}:{self.__password}@bioit-mongo-d01.{dtap_domain}:27017,bioit-mongo-d02.{dtap_domain}:27017,bioit-mongo-d03.{dtap_domain}:27017/?authSource={species}_{self.dtap}&replicaSet=bioit-HERA'
        return f'mongodb://admin:{self.__password}@bioit-mongo-d01.{dtap_domain}:27017,bioit-mongo-d02.{dtap_domain}:27017,bioit-mongo-d03.{dtap_domain}:27017/?replicaSet=bioit-HERA&authSource=admin'

    def get_azure_connection_string(self, species: str) -> str:
        """
        get azure connection string to mongo
        :return: connection string
        """
        dtap_extension = self._get_dtap_extension()
        if self.host_is_an_nrc_platform(species):
            return f'mongodb+srv://{self._get_user(species)}:{self.__password}@mongodb-atlas-{dtap_extension}-pl-0.fgpmn.mongodb.net/?retryWrites=true&w=majority'
        return f'mongodb+srv://admin:{self.__password}@mongodb-atlas-{dtap_extension}-pl-0.fgpmn.mongodb.net/?retryWrites=true&w=majority'

    def get_alternate_connection_string(self) -> str:
        """
        get alternate connection string to mongo
        :return: connection string
        """
        return self._mongo_global_config['CONNECTION_STRING_ALTERNATE']

    def is_viral(self, species: str) -> bool:
        """
        Check if the current species is viral
        :param species: species to evaluate
        :return: True if species is viral
        """
        return species in self._mongo_global_config['viral_species']

    def get_asb_connection_string(self) -> str:
        return self._mongo_global_config['CONNECTION_STRING_ASB']

    @staticmethod
    def get_all_species() -> List[str]:
        return ["enterococcus_faecalis",
                "enterococcus_faecium",
                "listeria",
                "mycobacterium",
                "neisseria",
                "stec",
                "salmonella",
                "influenza",
                "sars_cov_2"]

    def get_schemes_sequence_typing(self) -> List[str]:
        """
        get sequence typing schemes from the mongo db config
        """
        return self._mongo_global_config['schemes_sequence_typing']

    def get_naive_clustering_distance_matrix_file(self, species: str) -> str:
        """
        method to get naive clustering distance matrix file path
        :param species: species
        :return: a string referring to the distance matrix path
        """
        naive_clustering_distance_matrix_path = self._mongo_global_config['naive_clustering_distance_matrix_file'].replace('species', species).replace('dtap', self.dtap)
        return naive_clustering_distance_matrix_path

    def get_temp_dir(self) -> str:
        """
        get temp dir based on mongo config
        """
        return self._mongo_global_config['temp_dir']

    def get_azure_reportsapi_ip(self):
        """
        get azure reportsapi ip based on mongo config
        """
        return self._mongo_global_config['azure_reportsapi_ip']

    def get_mail(self):
        return self._mongo_global_config['mail']

    @staticmethod
    def host_is_an_nrc_platform(species: str) -> bool:
        platform_naming = f'bioit-nrc{species}'
        if platform_naming in f'{socket.gethostname()}':
            return True
        return False
