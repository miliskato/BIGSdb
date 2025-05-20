import sys
from pathlib import Path

from numpy import ndarray

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data

from bioit_bigsdb_scripts.components.psql import TblSequences, TblProfiles, TblProfileFields, TblProfileMembers, \
    TblClassificationGroups, TblClassificationGroupProfiles, TblClassificationGroupProfileHistory, \
    TblClassificationSchemes, TblIsolates, TblEavText, TblEavFields, TblSchemes
#

#
# # with TblProfiles('listeria') as seqdef_profiles_psql_tbl:
# #     # the following queries return empty lists: []
# #     print('###', seqdef_profiles_psql_tbl.execute(f"SELECT profile_id FROM profiles WHERE scheme_id=(SELECT id FROM schemes WHERE name='test');"))
# #     print('###', seqdef_profiles_psql_tbl.select_profile(('test',)))
#
# with TblSchemeMembers('listeria', 'isolates') as isolates_schememembers_psql_tbl:
#     print('###', isolates_schememembers_psql_tbl.select_loci_amr())
#
with TblIsolates('mycobacterium') as isolates_psql_tbl:
    test = isolates_psql_tbl.select_isolates_by_cgsts_and_between_dates((2, ['1', '2'], '2018-05-06', '2024-06-08'))
    print('###', test, len(test))
    print(test[0][2])
    test2 = isolates_psql_tbl.select_isolates_by_cgsts_and_between_dates((2, ['1', '2'], '2024-05-06', '2024-06-08'))
    print('###', test2, len(test2))

# with TblClassificationSchemes('stec', 'seqdef') as seqdef_clsch_psql_tbl:
#     print(seqdef_clsch_psql_tbl.select_cgschemes())
# bigsdb_config_data = get_bigsdb_config_data()
#
# dm_file = bigsdb_config_data['naive_clustering_distance_matrix_file'].replace('species', 'neisseria')
#
# from scipy.spatial.distance import pdist, squareform
# from scipy.cluster.hierarchy import linkage, dendrogram
# import numpy as np
#
# distance_matrix: np.array = np.load(str(dm_file))
# # distance_matrix = np.array([[0, 1, 2, 3],
# #                             [1, 0, 4, 5],
# #                             [2, 4, 0, 6],
# #                             [3, 5, 6, 0]])
# # print(squareform(distance_matrix))
# # print(linkage(squareform(distance_matrix), method='single', metric='hamming'))
# # print(linkage(squareform(distance_matrix), method='complete', metric='hamming'))
#
# import scipy.cluster.hierarchy as hcluster
# from scipy.spatial import distance as ssd
# import fastcluster
#
# slc: np.ndarray = fastcluster.single(ssd.squareform(distance_matrix))
# print(slc)
# print('shape', slc.shape)
# clc = fastcluster.complete(ssd.squareform(distance_matrix))
# print(clc)
# cluster_thresholds = {20}
# from sklearn.metrics import silhouette_score  # to install using scikit-learn
# for thresh in cluster_thresholds:
#     cluster_membership_slc = hcluster.fcluster(slc, thresh, criterion='distance')
#     print('shape', cluster_membership_slc.shape)
#     print('list', cluster_membership_slc.tolist())
#     print("nr of clusters slc", max(cluster_membership_slc))
#     print("silhouette score slc", silhouette_score(distance_matrix, cluster_membership_slc))
#     cluster_membership_clc: ndarray = hcluster.fcluster(clc, thresh, criterion='distance')
#     print("nr of clusters clc", max(cluster_membership_slc))
#     print("silhouette score clc", silhouette_score(distance_matrix, cluster_membership_clc))
#
# trues = 0
# falses = 0
# tolist1 = cluster_membership_slc.tolist()
# print(tolist1)
# tolist2 = cluster_membership_clc.tolist()
#
# for index, item in enumerate(tolist1):
#     count1 = tolist1.count(item)
#     count2 = tolist2.count(tolist2[index])
#     if count1 == count2:
#         trues+=1
#     else:
#         falses+=1
# print(f"same cluster: {trues}", f"diff cluster: {falses}")
#
#
# # from scipy.cluster.hierarchy import dendrogram
# # import matplotlib.pyplot as plt # todo needs to be installed, 3.8.2 by default in python3.9
# #
# # dendrogram(slc)
# # plt.savefig('slc_neiss.png')
# # plt.close()
# # dendrogram(clc)
# # plt.savefig('clc_neiss.png')
# # plt.close()
