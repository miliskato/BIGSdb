import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import List

import fastcluster
import hashlib
import numpy as np
import os
import scipy.cluster.hierarchy as hcluster
from scipy.spatial import distance as ssd

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblClassificationSchemes, TblClassificationGroups, \
    TblClassificationGroupProfiles, TblSchemes
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_mongodb_scripts.util.command.command import Command


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    argument_parser.add_argument("--linkage_method", required=False, type=str, choices=['single', 'complete'],
                                 default='complete')
    return argument_parser.parse_args()


class PeriodicalClustering:
    def __init__(self, species: str, linkage_method: str = 'complete') -> None:
        """
        Initialises the class and runs the main function.
        See also argparse function for variables and their requiredness.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param linkage_method: linkage method for clustering
        :return: None
        """
        # Input parameters
        self._species = species
        self._linkage_method = linkage_method
        self._bigsdb_config_data = get_bigsdb_config_data()
        self._dm_file = bigsdb_config_data['naive_clustering_distance_matrix_file'].replace('species', self._species)

        # Execute main function
        try:
            self._main_clustering()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f'{Path(__file__).name}: Error executing periodical clustering on host {socket.gethostname()}.')
            raise Exception(
                f'{Path(__file__).name}: Error executing periodical clustering on host {socket.gethostname()}.')

    def _main_clustering(self) -> None:
        """
        Main function; starting from a distance matrix file, calculates clusters across different thresholds
        (extracted from the bigsdb database) and inserts all clusters into the database.
        Function currently does not care if the distance matrix has changed since the last time it ran, because
        it runs so fast.
        In order to change this, a flagfile could be created that contains the md5 of the dm of the last run.
        :return: None
        """
        self.__check_dm_file_existence()
        self._linkage_matrix = self.__calculate_linkage_matrix()
        with TblClassificationSchemes(self._species, 'seqdef') as seqdef_clsch_psql_tbl:
            ids_and_thresholds = seqdef_clsch_psql_tbl.select_cgschemes()
            if len(ids_and_thresholds) == 0:
                logging.warning(f"No thresholds found. Exiting gracefully..")
                sys.exit()
        for id_and_threshold in ids_and_thresholds:
            cgscheme_id = int(id_and_threshold[0])
            threshold = int(id_and_threshold[1])
            cluster_membership_list = self.__assign_clusters_by_threshold(threshold)
            groups = set(cluster_membership_list)
            with TblClassificationGroups(self._species) as seqdef_clgr_psql_tbl:
                # by deleting the classfication groups, the corresponding classification group profiles are also deleted
                seqdef_clgr_psql_tbl.delete_groups((cgscheme_id,))
                for group_id in groups:
                    seqdef_clgr_psql_tbl.insert_group((str(cgscheme_id), str(group_id)))
            with TblClassificationGroupProfiles(self._species) as seqdef_clgrpr_psql_tbl:
                for index, cluster_group in enumerate(cluster_membership_list):
                    cgst = index + 1
                    seqdef_clgrpr_psql_tbl.insert_profile((str(cgscheme_id), str(cluster_group), str(cgst), 'cgMLST'))

    def __check_dm_file_existence(self):
        """
        Checks whether the distance matrix for the species exists.
        :return: None
        """
        if not Path(self._dm_file).is_file():
            raise FileNotFoundError(f"the distance matrix file {self._dm_file} could not be found, "
                                    f"hence the clustering could not be initialized")
        self.___check_flagile_and_md5()

    def ___check_flagile_and_md5(self) -> None:
        """
        Checks whether a flagfile containing the md5 exists for the distance matrix and whether the current distance
        matrix has a different md5. If the md5 is the same, the script exits gracefully.
        :return: None
        """
        path_flagfile = (Path(self._bigsdb_config_data['failsafe']['flag_dir']) / f"{Path(self._dm_file).stem}_md5.txt")
        md5_current_dm = hashlib.md5(np.load(self._dm_file).tobytes()).hexdigest()
        if not path_flagfile.is_file():
            pass
        else:
            with path_flagfile.open('r') as handle:
                md5_dm = handle.read()
            if md5_dm == md5_current_dm:
                logging.warning(f"Md5 of previous version of distance matrix and md5 of the current version are the "
                                f"same. Exiting gracefully..")
                sys.exit()
        with path_flagfile.open('w') as handle:
            handle.write(md5_current_dm)

    def __calculate_linkage_matrix(self) -> np.ndarray:
        """
        From the input distance matrix, calculates the linkage matrix representing the hierarchical clustering of
        the data using the chosen linkage method.
        :return: the linkage matrix for the given input distance matrix
        """
        distance_matrix: np.array = np.load(self._dm_file)
        linkage_matrix = fastcluster.linkage(ssd.squareform(distance_matrix), method=self._linkage_method)
        return linkage_matrix

    def __assign_clusters_by_threshold(self, threshold: int) -> object:
        """
        Uses the previously calculated linkage matrix to assign all cgSTs to clusters according to a certain threshold
        :return: List of the cluster memberships for all cgSTs in chronological order. The type of tolist() is dynamic,
        hence the object in the return, but the actual return is List[int, ...]
        """
        cluster_membership_list = hcluster.fcluster(self._linkage_matrix, threshold, criterion='distance').tolist()
        return cluster_membership_list


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))

    # run main
    PeriodicalClustering(args.species, args.linkage_method)

    # update the bigsdb cache so the clustering schemes get updated
    with TblSchemes(args.species, 'isolates') as isolates_schemes_psql_tbl:
        cgmlst_bigsdb_scheme_id = isolates_schemes_psql_tbl.select_scheme_id_cgmlst()[0][0]
    cache_command = f'/home/bigsdb/BIGSdb/scripts/maintenance/update_scheme_caches.pl ' \
                    f'--database bigsdb_{args.species}_isolates --schemes {cgmlst_bigsdb_scheme_id}'
    cache_command_object = Command(cache_command)
    cache_command_object.run(Path(os.getcwd()))
    if cache_command_object.returncode != 0:
        send_email(f"update of the cache to display the clustering failed on host {socket.gethostname()}")
        raise RuntimeError(f"update of the cache to display the clustering failed on host {socket.gethostname()}")
