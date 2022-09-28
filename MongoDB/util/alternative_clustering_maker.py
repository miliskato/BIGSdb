import numpy as np
import pymongo
import fastcluster
import plotly.figure_factory as ff
import plotly
from scipy.spatial import distance as ssd
import scipy.cluster.hierarchy as hcluster
import matplotlib.pyplot as plt
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.clustering_maker import ClusteringMaker


class AlternativeClusteringMaker(ClusteringMaker):
    def __init__(self, hiercc_collection, isolates_collection, isolate_results_collection, hc: int, sample: str,
                 cluster: int):
        self.hiercc_results_collection = hiercc_collection
        self.isolates_collection = isolates_collection
        self.isolate_results_collection = isolate_results_collection
        self.sample = sample
        self.sample_st = self._retrieve_sample_st()
        self.hc = f"HC{hc}"
        self.hc_number = cluster
        self.cluster_members_st = [self.sample_st]
        self._retrieve_cluster_members_st()
        self.cluster_members_samples = []
        self.cgmlst_profiles = []
        self._retrieve_cluster_members_samples_and_profiles()
        self.hamming_distances = []
        self.compute_hamming_distances('full')
        self.hamming_distances += self.hamming_distances.T

    def single_linkage_clustering(self) -> None:
        slc = fastcluster.single(ssd.squareform(self.hamming_distances))
        names = self.cluster_members_samples
        dist = self.hamming_distances / 2
        save_name = f'{self.sample}_{self.hc}_alternative_cluster_{self.hc_number}'
        fig = ff.create_dendrogram(dist, orientation='left', labels=names, color_threshold=int(self.hc.replace('HC','')))
        fig.update_layout(width=800, height=500)
        plotly.offline.plot(fig, filename=f"{save_name}.html", auto_open=False)
        dn = hcluster.dendrogram(slc, leaf_rotation=90, labels=names, leaf_font_size=8, show_leaf_counts=False)
        plt.savefig(f'{save_name}.png', format='png', bbox_inches='tight')
        plt.savefig(f'{save_name}.jpg', format='jpg', bbox_inches='tight')
        tree = hcluster.to_tree(slc)
        newick = ClusteringMaker.get_newick(tree, tree.dist, names)
        with open(f'{save_name}_tree.newick', 'w') as file:
            file.write(newick)
