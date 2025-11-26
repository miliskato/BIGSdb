from pathlib import Path
from typing import Any

import yaml

from bioit_mongodb_scripts.config import CLUSTERING_CONFIG


class MongoClusteringConfigProvider:
    """
    Class to facilitate access to the tresholds used for the clustering.
    """
    __CURRENTLY_SUPPORTED_SPECIES = ["enterococcus_faecalis",
                                     "enterococcus_faecium",
                                     "listeria",
                                     "mycobacterium",
                                     "neisseria",
                                     "salmonella",
                                     "influenza",
                                     "sars_cov_2"]

    def __init__(self, species: str):
        """
        :return: None
        """
        self._species = species
        self._mongo_clustering_config = self._get_mongodb_clustering_config()

    @staticmethod
    def _get_mongodb_clustering_config() -> dict[str, str | list[Any] | dict[str, str | dict[str, Any]]]:
        """
        Reads the mongo db config file
        :return: dict containing the config items
        """
        with Path(CLUSTERING_CONFIG).open('r') as handle:
            mongo_clustering_config = yaml.safe_load(handle)
        return mongo_clustering_config

    def get_clustering_thresholds(self) -> list[int]:
        """
        Returns the clustering thresholds for the species
        :return: list of int with the thresholds
        """
        thresholds_field = f'clustering_thresholds_{self._species}'
        return self._mongo_clustering_config[thresholds_field]

    def get_lowest_clustering_threshold(self) -> int:
        """
        Returns the lowest threshold for the species
        :return: int with the lowest threshold
        """
        thresholds = self.get_clustering_thresholds()
        return min(thresholds)

    def get_highest_clustering_threshold(self) -> int:
        """
        Returns the highest threshold for the species
        :return: int with the highest threshold
        """
        thresholds = self.get_clustering_thresholds()
        return max(thresholds)

    def get_allowed_proportion_of_missing_alleles(self) -> float:
        """
        Returns the allowed proportion of missing alleles for the species
        :return: float with the allowed proportion of missing alleles
        """
        return float(self._mongo_clustering_config['allowed_missing_data_proportion'])
