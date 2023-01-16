import logging
from pathlib import Path
from typing import Dict, List, Union

import yaml

from MongoDB.util.distance_and_cluster_computer import DistanceAndClusterComputer


class NewThresholdClustering(DistanceAndClusterComputer):
    def __init__(self, st_collection: object, cluster_membership_collection: object, clustering_config_file: Path, new_thresholds: list,
                 species: str) -> None:
        """
        Init of the class
        :param st_collection: the sequence type collection of Mongo db
        :param cluster_membership_collection:  the cluster membership collection of mongo db
        :param clustering_config_file:  the path to the clustering config file
        :param new_thresholds: new threshold (max number of differences accepted to be part of the same cluster)
        :param species: species to which we want to add new thresholds
        """
        self.config_file_path = clustering_config_file
        self.new_clustering_thresholds = new_thresholds
        self.species = species
        super().__init__(st_collection, cluster_membership_collection, [0])

    def create_new_threshold_and_compute_clustering(self) -> None:
        """
        add new threshold to the clustering config file and compute the clustering for the new thresholds.
        :return: None
        """
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Loading the config file")
        clustering_config = self._load_config_file()
        logging.info("Checking if the new thresholds are absent from the config")
        species_thresh_field = f'clustering_thresholds_{self.species}'
        thresh_to_add = []
        for threshold in self.new_clustering_thresholds:
            if int(threshold) not in clustering_config[species_thresh_field]:
                thresh_to_add.append(int(threshold))
            else:
                logging.info(f"The threshold {threshold} is already in the config file, it will not be added")
        if not thresh_to_add:
            logging.info(f"None of the thresholds needed to be added => No further actions")
        else:
            logging.info(f"The following thresholds will be added : {thresh_to_add}")
            clustering_config[species_thresh_field] = clustering_config[species_thresh_field] + thresh_to_add
            self._write_config_file(clustering_config)
            logging.info(f"New config file written")
            logging.info(f"Clustering of the sequence types of the database to the new thresholds")
            self.compute_hamming_distances('full')
            logging.info(f"Compute cluster membership and save them to the database")
            self.init_clustering_and_cluster_membership(thresh_to_add)
            logging.info(f"New clustering completed successfully!")

    def _load_config_file(self) -> Dict[str, Union[float, int, List[Union[int, float]]]]:
        """
        loads the clustering config file
        :return: dict with the loaded config file informations
        """
        with open(self.config_file_path) as handle:
            clustering_config = yaml.load(handle, Loader=yaml.SafeLoader)
        return clustering_config

    def _write_config_file(self, config: dict) -> None:
        """
        write the config file with the new clustering informations.
        :param config: dict containing the information of the config files to be loaded.
        :return: None
        """
        with open(self.config_file_path, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False)
