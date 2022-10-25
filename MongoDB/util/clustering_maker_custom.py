import numpy as np
import pymongo
import fastcluster
import plotly.figure_factory as ff
import plotly
from scipy.spatial import distance as ssd
import scipy.cluster.hierarchy as hcluster
import matplotlib.pyplot as plt
from MongoDB.util.mongo_querying_old import Mongoquerying
from MongoDB.util.distance_and_cluster_computer import DistanceAndClusterComputer
from MongoDB.util.hamming_distance import getDistance
from multiprocessing import Pool

class ClusteringMakerCustom(DistanceAndClusterComputer):
    def __init__(self, cluster_membership_collection, isolates_collection, threshold: int, sample: str):
        self.cluster_membership_collection = cluster_membership_collection
        self.isolates_collection = isolates_collection
        self.sample = sample
        self.sample_st = self._retrieve_sample_st()
        print(self.sample_st)
        self.threshold = threshold
        self.cluster_membership = self.__retrieve_cluster_membership()
        self.cluster_members_st = []
        self._retrieve_cluster_members_st()
        self.cluster_members_samples = []
        self.cgmlst_profiles = []
        self._retrieve_cluster_members_samples_and_profiles()
        self.hamming_distances = []
        self.compute_hamming_distances()
        self.hamming_distances = [matrix + matrix.T for matrix in self.hamming_distances]

    def _retrieve_sample_st(self) -> int:
        return self.isolates_collection.find_one({'_id': self.sample})['ST']

    def __retrieve_cluster_membership(self) -> int:
        return self.cluster_membership_collection.find_one({'ST': self.sample_st, 'Threshold': self.threshold})['Clustering_membership']

    def _retrieve_cluster_members_st(self) -> None:
        if self.mode == 'split_cluster':
            for cl in self.cluster_membership:
                cluster_st = self.cluster_membership_collection.find({'Clustering_membership': cl, 'Threshold': self.threshold})
                self.cluster_members_st.append(ClusteringMakerCustom.extract_field_in_find_query(cluster_st,'ST'))
        else:
            query_st = self.cluster_membership_collection.find({'Clustering_membership': {'$in': self.cluster_membership}, 'Threshold': self.threshold})
            self.cluster_members_st.append(ClusteringMakerCustom.extract_field_in_find_query(query_st, 'ST'))
            self.cluster_members_st[0] = list(set(self.cluster_members_st[0])) #to have unique values

    @staticmethod
    def extract_field_in_find_query(query, field:str) ->list:
        fields_extracted = []
        for result in query:
            fields_extracted.append(result[field])
        return fields_extracted

    def _retrieve_cluster_members_samples_and_profiles(self) -> None:
        for st_collection in self.cluster_members_st:
            print(st_collection)
            cgmlst_collection = []
            sample_collection = []
            for st in st_collection:
                query_samples = self.isolates_collection.find({'ST': st})
                for res in query_samples:
                    sample_id = res['_id']
                    mongoquerying = Mongoquerying()
                    query_profile = mongoquerying._query_typing_results_by_technicalids_and_scheme(
                        self.isolates_collection,
                        self.isolate_results_collection,
                        scheme="cgmlst",
                        technicalids=
                        [sample_id])
                    # next step is to order the alleles by allele names to be sure that all profiles are in the same order.
                    #ordered_alleles = [x for _, x in sorted(zip(query_profile[0][1:], query_profile[1][1:]))]
                    cgmlst_collection.append(np.array(query_profile[1][1:]))
                    sample_collection.append(sample_id)
            self.cgmlst_profiles.append(np.array(cgmlst_collection))
            self.cluster_members_samples.append(sample_collection)

    def compute_hamming_distances(self) -> None:
        """
        Compute the hamming distances between sequence types
        :param mode: full is to compute all the distances against all the cgmlst in the db while
        last_st computes only for the last sequence types entered in the db.
        :return:
        """
        for collection in self.cgmlst_profiles:
            start = 0
            pool = Pool(4)
            self.hamming_distances.append(getDistance(np.array(collection), 'hamming_dist', pool, start))

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
            newick = ClusteringMakerCustom.get_newick(node.get_left(), node.dist, leaf_names, newick=newick)
            newick = ClusteringMakerCustom.get_newick(node.get_right(), node.dist, leaf_names, newick=",%s" % (newick))
            newick = "(%s" % (newick)
            return newick

    def single_linkage_clustering(self) -> None:
        for clustering in range(len(self.hamming_distances)):
            slc = fastcluster.single(ssd.squareform(self.hamming_distances[clustering]))
            names = self.cluster_members_samples[clustering]
            print(self.hamming_distances[clustering])
            print(names)
            dist = self.hamming_distances[clustering] / 2
            if self.mode == 'extended_cluster':
                cluster_name = '_'.join([str(cl) for cl in self.cluster_membership])
            else:
                cluster_name = self.cluster_membership[clustering]
            save_name = f'{self.sample}_{self.threshold}_cluster_{cluster_name}'
            fig = ff.create_dendrogram(dist, orientation='left', labels=names,
                                       color_threshold=int(self.threshold))
            fig.update_layout(width=800, height=500)
            plotly.offline.plot(fig, filename=f"{save_name}.html", auto_open=False)
            dn = hcluster.dendrogram(slc, leaf_rotation=90, labels=names, leaf_font_size=8, show_leaf_counts=False)
            plt.savefig(f'{save_name}.png', format='png', bbox_inches='tight')
            plt.savefig(f'{save_name}.jpg', format='jpg', bbox_inches='tight')
            tree = hcluster.to_tree(slc)
            newick = ClusteringMakerCustom.get_newick(tree, tree.dist, names)
            with open(f'{save_name}_tree.newick', 'w') as file:
                file.write(newick)
            plt.clf()