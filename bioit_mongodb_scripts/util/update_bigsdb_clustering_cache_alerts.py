import os
from pathlib import Path
from typing import Union

from bioit_mongodb_scripts.util.alerts_to_bigs import AlertsToBigs
from bioit_mongodb_scripts.util.new_clustering_info_to_bigs import NewClusteringInfoToBigs
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.python_utility_functions import execute_command, get_cgmlst_bigsdb_scheme_id


class UpdateBIGSdbClusteringCacheAlerts:
    """
    Updates the clustering info, the cache and the alerts in BIGSdb.
    """

    def __init__(self, species: str, list_of_new_isolates_for_alerts: list[dict[str, Union[str, int]]],
                 list_of_new_versions_for_alerts: list[dict[str, Union[str, int]]]) -> None:
        """
        Initializes the class.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param list_of_new_isolates_for_alerts: List of dictionaries of relevant data concerning newly
        sql-inserted isolates.
        :param list_of_new_versions_for_alerts: List of dictionaries of relevant data concerning newly
        sql-inserted versions of existing isolates with different cgSTs than the previous version.
        :return: None
        """
        self._mongo_config_provider = MongoConfigProvider()
        self._species = species
        self._cgmlst_bigsdb_scheme_id = get_cgmlst_bigsdb_scheme_id(self._species)
        self._distance_matrix = Path(self._mongo_config_provider.get_naive_clustering_distance_matrix_file(self._species))
        self._list_of_new_isolates_for_alerts = list_of_new_isolates_for_alerts
        self._list_of_new_versions_for_alerts = list_of_new_versions_for_alerts

    def update_clustering_cache_alerts(self) -> None:
        """
        Executes the new clustering info to bigs, updates the cache and runs the alerts to bigs.
        :return: None
        """
        NewClusteringInfoToBigs(self._species, self._distance_matrix, self._cgmlst_bigsdb_scheme_id, self._mongo_config_provider)
        self._update_cache('incremental')
        AlertsToBigs(self._list_of_new_isolates_for_alerts, self._list_of_new_versions_for_alerts, self._species, self._cgmlst_bigsdb_scheme_id, self._distance_matrix)

    def _update_cache(self, method: str) -> None:
        """
        Updates the BIGSdb cache.
        :param method: which method to use to update the cache
        :return: None
        """
        cache_command = f'/home/bigsdb/BIGSdb/scripts/maintenance/update_scheme_caches.pl ' \
                        f'--database bigsdb_{self._species}_isolates --schemes {self._cgmlst_bigsdb_scheme_id} ' \
                        f'--method {method}'
        execute_command(cache_command, Path(os.getcwd()))
