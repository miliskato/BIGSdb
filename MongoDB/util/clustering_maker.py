import numpy as np
import pymongo
import fastcluster
import plotly.figure_factory as ff
import plotly
from scipy.spatial import distance as ssd
import scipy.cluster.hierarchy as hcluster
import matplotlib.pyplot as plt

class ClusteringMaker:
    def __init__(self, hiercc_collection, distance_matrix_collection, hc: int, hc_number: int):
        self.hiercc_results_collection = hiercc_collection
        self.distance_matrix_collection = distance_matrix_collection
        self.hc = f"HC{hc}"
        self.hc_number = hc_number
        self.cluster_members = []
        self.__retrieve_cluster_members()
        self.distance_matrix = np.array([])

    def __retrieve_cluster_members(self) -> None:
        query = self.hiercc_results_collection.find({'HC': self.hc, 'HC_number': self.hc_number})
        for result in query:
            self.cluster_members.append(result['ST'])
        self.cluster_members.sort()

    def retrieve_matrix_from_cluster(self) -> None:
        nrow_col = len(self.cluster_members)
        self.distance_matrix = np.zeros((nrow_col, nrow_col))
        for i in range(nrow_col):
            for j in range(i):
                self.distance_matrix[i,j] = self.distance_matrix_collection.find_one({'I': self.cluster_members[i],'J': self.cluster_members[j]})['Hamming_distance']
        self.distance_matrix += self.distance_matrix.T
        print(self.distance_matrix)

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
            newick = get_newick(node.get_left(), node.dist, leaf_names, newick=newick)
            newick = get_newick(node.get_right(), node.dist, leaf_names, newick=",%s" % (newick))
            newick = "(%s" % (newick)
            return newick

    def single_linkage_clustering(self,save_name: str) -> None:
        if len(self.distance_matrix) == 0:
            raise ValueError('self.distance_matrix is empty. Impossible to run the clustering')
        else:
            print(ssd.squareform(self.distance_matrix))
            slc = fastcluster.single(ssd.squareform(self.distance_matrix))
            names = [f"ST{i}" for i in self.cluster_members]
            # fig = ff.create_dendrogram(self.distance_matrix, orientation='left', labels=names, color_threshold=10)
            # fig.update_layout(width=800, height=500)
            # plotly.offline.plot(fig, filename=f"/home/bebergk/{save_name}.html")
            # plt.figure()
            # dn = hcluster.dendrogram(slc, leaf_rotation=90, labels=names,  leaf_font_size=8, show_leaf_counts=False)
            # plt.savefig('plt.png', format='png', bbox_inches='tight')
            # plt.savefig('plt.jpg', format='jpg', bbox_inches='tight')
            tree = hcluster.to_tree(slc)
            newick = self.get_newick(tree, tree.dist, names)
            with open('test_tree.newick','w') as file:
                file.write(newick)



