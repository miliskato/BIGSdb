import logging

import fastcluster
import matplotlib.pyplot as plt
import numpy as np
import plotly
import plotly.figure_factory as ff
import pymongo
import scipy
import scipy.cluster.hierarchy as hcluster
from scipy.spatial import distance as ssd

from bioit_mongodb_scripts.util.distance_and_cluster_computer import DistanceAndClusterComputer
from bioit_mongodb_scripts.util.mongo_querying import Mongoquerying


class ClusteringMakerCustom(DistanceAndClusterComputer):
    def __init__(self, cluster_membership_collection: pymongo.collection.Collection, isolates_collection: pymongo.collection.Collection,
                 hashed_AD_collection: pymongo.collection.Collection, threshold: int, sample: str) -> None:
        """
        Init of the class
        :param cluster_membership_collection: collection where the cluster membership of the ST is stored
        :param isolates_collection: collection where results from the isolates is stored
        :param hashed_AD_collection: collection where the new alleles are stored
        :param threshold: threshold to use to reconstruct the cluster (number of differences between cgmlst profiles tolerated to be part of the same cluster).
        :param sample: sample to extract the cluster membership and reconstruct the cluster.
        """
        logging.getLogger().setLevel(logging.INFO)
        logging.info("Initialization of the clustering maker custom")
        self.cluster_membership_collection = cluster_membership_collection
        self.isolates_collection = isolates_collection
        self.hashed_AD_collection = hashed_AD_collection
        self.sample = sample
        self.sample_st = self._retrieve_sample_st()
        self.threshold = threshold
        self.cluster_membership = self._retrieve_cluster_membership()
        self.cluster_members_st = []
        self._retrieve_cluster_members_st()
        self.cluster_members_samples = []
        self.cgmlst_profiles = []
        logging.info("Retrieving cluster members and cgMLST profiles")
        self._retrieve_cluster_members_samples_and_profiles()
        self.hamming_distances = []
        logging.info("Computing hamming distances")
        self.compute_hamming_distances('full')

    def _retrieve_sample_st(self) -> int:
        """
        Retrieve the sequence type of the sample.
        :return: the sequence type which is an int.
        """
        return self.isolates_collection.find_one({'_id': self.sample})['results']['cgST']

    def _retrieve_cluster_membership(self) -> int:
        """
        Retrieve the cluster membership of the sample self.sample.
        :return: the cluster membership which is an int.
        """
        return self.cluster_membership_collection.find_one({'cgST': self.sample_st, 'threshold': self.threshold})[
            'clustering_membership']

    def _retrieve_cluster_members_st(self) -> None:
        """
        Retrieve all the sequence types which are part of the cluster from the sample self.sample.
        :return: None
        """
        self.cluster_members = list(self.cluster_membership_collection.find(
            {'clustering_membership': self.cluster_membership, 'threshold': self.threshold}, {'cgST': 1, '_id': 0}))
        self.cluster_members_st = [x['cgST'] for x in self.cluster_members]

    def _retrieve_cluster_members_samples_and_profiles(self) -> None:
        """
        Retrieve the samples which are members of the cluster and their cgmlst proviles
        :return:  None
        """
        for st in self.cluster_members_st:
            query_samples = self.isolates_collection.find({'results.cgST': st})
            for res in query_samples:
                sample_id = res['_id']
                if res == query_samples[0]:
                    mongoquerying = Mongoquerying()
                    query_profile = mongoquerying.query_typing_results_by_technicalids_and_scheme(
                    self.isolates_collection,
                    self.hashed_AD_collection,
                    scheme="cgmlst",
                    technicalids=
                    [sample_id])
                # next step is to order the alleles by allele names to be sure that all profiles are in the same order.
                # ordered_alleles = [x for _, x in sorted(zip(query_profile[0][1:], query_profile[1][1:]))]
                self.cgmlst_profiles.append(np.array(query_profile[1][1:]))
                self.cluster_members_samples.append(sample_id)
        self.cgmlst_profiles = np.array(self.cgmlst_profiles)

    @staticmethod
    def get_newick(node: scipy.cluster.hierarchy.ClusterNode, parent_dist: float, leaf_names: list, newick: str = '') -> str:
        """
        Convert sciply.cluster.hierarchy.to_tree()-output to Newick format.
        :param node: output of sciply.cluster.hierarchy.to_tree()
        :param parent_dist: output of sciply.cluster.hierarchy.to_tree().dist
        :param leaf_names: list of leaf names
        :param newick: leave empty, this variable is used in recursion.
        :returns: tree in Newick format.
        """
        if node.is_leaf():
            return "%s:%.2f%s" % (leaf_names[node.id], parent_dist - node.dist, newick)
        else:
            if len(newick) > 0:
                newick = "):%.2f%s" % (parent_dist - node.dist, newick)
            else:
                newick = ");"
            newick = ClusteringMakerCustom.get_newick(node.get_left(), node.dist, leaf_names, newick=newick)
            newick = ClusteringMakerCustom.get_newick(node.get_right(), node.dist, leaf_names, newick=",%s" % newick)
            newick = "(%s" % newick
            return newick

    def single_linkage_clustering(self) -> None:
        slc = fastcluster.single(ssd.squareform(self.hamming_distances))
        names = self.cluster_members_samples
        dist = self.hamming_distances / 2
        cluster_name = self.cluster_membership
        save_name = f'{self.sample}_{self.threshold}_cluster_{cluster_name}'
        fig = ff.create_dendrogram(dist, orientation='left', labels=names,
                                   color_threshold=int(self.threshold))
        fig.update_layout(width=800, height=500)
        plotly.offline.plot(fig, filename=f"{save_name}.html", auto_open=False)
        #dn = hcluster.dendrogram(slc, leaf_rotation=90, labels=names, leaf_font_size=8, show_leaf_counts=False)
        plt.savefig(f'{save_name}.png', format='png', bbox_inches='tight')
        plt.savefig(f'{save_name}.jpg', format='jpg', bbox_inches='tight')
        tree = hcluster.to_tree(slc)
        newick = ClusteringMakerCustom.get_newick(tree, tree.dist, names)
        with open(f'{save_name}_tree.newick', 'w') as file:
            file.write(newick)
        plt.clf()
