import numpy as np
import pymongo
import fastcluster
import plotly.figure_factory as ff
import plotly
from scipy.spatial import distance as ssd
import scipy.cluster.hierarchy as hcluster
import matplotlib.pyplot as plt
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.distance_matrix_computer import DistanceMatrixComputer


class ClusteringMaker(DistanceMatrixComputer):
    def __init__(self, hiercc_collection, isolates_collection, isolate_results_collection, hc: int, sample: str):
        self.hiercc_results_collection = hiercc_collection
        self.isolates_collection = isolates_collection
        self.isolate_results_collection = isolate_results_collection
        self.sample = sample
        self.sample_st = self._retrieve_sample_st()
        self.hc = f"HC{hc}"
        self.hc_number = self.__retrieve_hc_cluster()
        self.cluster_members_st = []
        self._retrieve_cluster_members_st()
        self.cluster_members_samples = []
        self.cgmlst_profiles = []
        self._retrieve_cluster_members_samples_and_profiles()
        self.hamming_distances = []
        self.compute_hamming_distances('full')
        self.hamming_distances += self.hamming_distances.T

    def _retrieve_sample_st(self) -> int:
        return self.isolates_collection.find_one({'_id': self.sample})['HierCC_ST']

    def __retrieve_hc_cluster(self) -> int:
        return self.hiercc_results_collection.find_one({'ST': self.sample_st, 'HC': self.hc})['HC_number']

    def _retrieve_cluster_members_st(self) -> None:
        query = self.hiercc_results_collection.find({'HC': self.hc, 'HC_number': self.hc_number})
        for result in query:
            self.cluster_members_st.append(result['ST'])
        self.cluster_members_st.sort()

    def _retrieve_cluster_members_samples_and_profiles(self) -> None:
        for st in self.cluster_members_st:
            query_samples = self.isolates_collection.find({'HierCC_ST': st})
            for res in query_samples:
                sample_id = res['_id']
                mongoquerying = Mongoquerying()
                query_profile = mongoquerying._query_typing_results_by_technicalids_and_scheme(self.isolates_collection,
                                                                                          self.isolate_results_collection,
                                                                                          scheme="cgmlst",
                                                                                          technicalids=
                                                                                          [sample_id])
                #next step is to order the alleles by allele names to be sure that all profiles are in the same order.
                ordered_alleles = [x for _,x in sorted(zip(query_profile[0][1:],query_profile[1][1:]))]
                self.cgmlst_profiles.append(np.array(ordered_alleles))
                self.cluster_members_samples.append(sample_id)
        self.cgmlst_profiles = np.array(self.cgmlst_profiles)

    @staticmethod
    def get_newick(node, parent_dist, leaf_names, newick='') -> str:
        """
        Convert sciply.cluster.hierarchy.to_tree()-output to Newick format.

        :param node: output of sciply.cluster.hierarchy.to_tree()
        :param parent_dist: output of sciply.cluster.hierarchy.to_tree().dist
        :param leaf_names: list of leaf names
        :param newick: leave empty, this variable is used in recursion.
        :returns: tree in Newick format
        """
        if node.is_leaf():
            return "%s:%.2f%s" % (leaf_names[node.id], parent_dist - node.dist, newick)
        else:
            if len(newick) > 0:
                newick = "):%.2f%s" % (parent_dist - node.dist, newick)
            else:
                newick = ");"
            newick = ClusteringMaker.get_newick(node.get_left(), node.dist, leaf_names, newick=newick)
            newick = ClusteringMaker.get_newick(node.get_right(), node.dist, leaf_names, newick=",%s" % (newick))
            newick = "(%s" % (newick)
            return newick

    def single_linkage_clustering(self) -> None:
        slc = fastcluster.single(ssd.squareform(self.hamming_distances))
        names = self.cluster_members_samples
        dist = self.hamming_distances/2
        save_name = f'{self.sample}_{self.hc}'
        fig = ff.create_dendrogram(dist, orientation='left', labels=names, color_threshold=int(self.hc.replace('HC','')))
        fig.update_layout(width=800, height=500)
        plotly.offline.plot(fig, filename=f"{save_name}.html", auto_open=False)
        dn = hcluster.dendrogram(slc, leaf_rotation=90, labels=names,  leaf_font_size=8, show_leaf_counts=False)
        plt.savefig(f'{save_name}.png', format='png', bbox_inches='tight')
        plt.savefig(f'{save_name}.jpg', format='jpg', bbox_inches='tight')
        tree = hcluster.to_tree(slc)
        newick = ClusteringMaker.get_newick(tree, tree.dist, names)
        with open(f'{save_name}_tree.newick', 'w') as file:
            file.write(newick)