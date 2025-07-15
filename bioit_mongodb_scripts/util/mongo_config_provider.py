import socket
import sys
from pathlib import Path
from typing import Any, Literal

import yaml

from bioit_bigsdb_scripts.utils.literal_helper import validate_literal

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import MONGO_CONFIG


DtapValues = Literal['dev', 'test', 'acc', 'prod']
DtapValue = str | DtapValues  # workaround to avoid pycharm warnings


class MongoConfigProvider:
    """
    Class to facilitate access to the different parts of the global mongodb config.
    """

    def __init__(self, alternate_dtap: DtapValue | None = None):
        """
        :param alternate_dtap: optional dtap if need to overwrite the config
        :return: None
        """
        if alternate_dtap:
            validate_literal(alternate_dtap, DtapValues)
        self._mongo_global_config = self._get_mongodb_config_data()
        self.dtap = self._mongo_global_config['dtap'] if alternate_dtap is None else str(alternate_dtap)
        self.__password = self._mongo_global_config['MONGO_DB_PASSWORD']
        self.upload_path = 'upload/' + f"{(alternate_dtap + '/') if alternate_dtap else ''}"

    @staticmethod
    def _get_mongodb_config_data() -> dict[str, str | list[Any] | dict[str, str | dict[str, Any]]]:
        """
        Reads the mongo db config file
        :return: dict containing the config items
        """
        with Path(MONGO_CONFIG).open('r') as handle:
            mongo_config_data = yaml.safe_load(handle)
        return mongo_config_data

    def _get_user(self, species: str) -> str:
        """
        Return the MongoDB user string for this particular species and dtap
        :param species: the current species name
        :return: a string corresponding to the MongoDB user
        """
        return f'{species}User_{self.dtap}'

    def get_local_connection_string(self, species: str) -> str:
        """
        Get connection string to the local cluster of MongoDB
        :return: connection string
        """
        domain = 'darwinproject.be' if self.dtap in ['dev', 'test'] else 'sciensano.be'
        ext = 'd' if self.dtap in ['dev', 'test'] else 'p'
        if self.host_is_an_nrc_platform(species):
            return f'mongodb://{self._get_user(species)}:{self.__password}@bioit-mongo-{ext}01.{domain}:27017,bioit-mongo-{ext}02.{domain}:27017,bioit-mongo-{ext}03.{domain}:27017/?authSource={species}_{self.dtap}&replicaSet=bioit-HERA'

        return f'mongodb://admin:{self.__password}@bioit-mongo-{ext}01.{domain}:27017,bioit-mongo-{ext}02.{domain}:27017,bioit-mongo-{ext}03.{domain}:27017/?replicaSet=bioit-HERA&authSource=admin'

    def get_azure_connection_string(self, species: str) -> str:
        """
        Get connection string to MongoDB Atlas cluster
        :return: connection string
        """
        dtap_extension = 'devtest' if self.dtap in ['dev', 'test'] else 'accprod'
        domain = 'fgpmn' if self.dtap in ['dev', 'test'] else 'lw3rk'
        if self.host_is_an_nrc_platform(species):
            return f'mongodb+srv://{self._get_user(species)}:{self.__password}@mongodb-atlas-{dtap_extension}-pl-0.{domain}.mongodb.net/?retryWrites=true&w=majority'
        return f'mongodb+srv://admin:{self.__password}@mongodb-atlas-{dtap_extension}-pl-0.{domain}.mongodb.net/?retryWrites=true&w=majority'

    @property
    def alternate_connection_string(self) -> str:
        """
        Get alternate connection string contains in the config file for MongoDB
        :return: connection string
        """
        return self._mongo_global_config['CONNECTION_STRING_ALTERNATE']

    def is_viral(self, species: str) -> bool:
        """
        Check if the current species is viral
        :param species: species to evaluate
        :return: True if species is viral
        """
        return species in self.get_current_viral_species()

    @property
    def asb_connection_string(self) -> str:
        """
        Get the connection string for Azure Service Bus
        :return: connection string to Azure Service Bus
        """
        return self._mongo_global_config['CONNECTION_STRING_ASB']

    @staticmethod
    def get_currently_supported_species() -> list[str]:
        """
        Get the list of all currently supported species
        :return: a list of all currently used species
        """
        return ["enterococcus_faecalis",
                "enterococcus_faecium",
                "listeria",
                "mycobacterium",
                "neisseria",
                "salmonella",
                "influenza",
                "sars_cov_2"]

    @staticmethod
    def get_current_viral_species() -> list[str]:
        """
        Get the list of all currently supported viral species
        :return: a list of all currently supported viral species
        """
        return ["influenza", "sars_cov_2"]

    @property
    def sequence_typing_schemes(self) -> list[str]:
        """
        get sequence typing schemes from the mongo db config
        :return: a list of sequence typing schemes
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

    @property
    def temp_dir(self) -> str:
        """
        get temp dir based on mongo config
        :return: a string referring to the temp dir
        """
        return self._mongo_global_config['temp_dir']

    @property
    def azure_reportsapi_ip(self) -> str:
        """
        get azure reportsapi ip address based on mongo config
        :return: a string referring to the azure reportsapi ip address
        """
        return self._mongo_global_config['azure_reportsapi_ip']

    @property
    def mail_info(self) -> str:
        """
        get email address to send the log
        :return: a string referring to the email address
        """
        return self._mongo_global_config['mail']

    @property
    def json_reports_dir(self) -> str:
        """
        get json reports dir based on mongo config
        :return: a string referring to the json reports dir
        """
        return self._mongo_global_config['json_reports_dir']

    @staticmethod
    def host_is_an_nrc_platform(species: str) -> bool:
        """
        Check if the current host is a VM used for the deployment of NRC platform
        :param species: species
        :return: True if current host is a VM used for the deployment of NRC platform
        """
        platform_naming = f'bioit-nrc{species[:3]}'
        if platform_naming in f'{socket.gethostname()}':
            return True
        return False
