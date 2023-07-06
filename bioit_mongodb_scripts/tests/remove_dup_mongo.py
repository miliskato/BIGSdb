import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


if __name__ == '__main__':

    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Open collections
    _mongoinit = MongoInitialisation('neisseria',
                                          alternate_connection_string=mongo_config_data.get('CONNECTION_STRING'),
                                          mongo_config_data=mongo_config_data)
    _isolates_collection, _old_isolateresults_collection, _isolates_badqc_collection, \
    _isolates_resequencing_collection = _mongoinit.initialise_collections()
    _st_collection, _cluster_membership_collection, _cluster_merging_collection = \
        _mongoinit.initialise_clustering_collections()

    all_st_cgmlst = _st_collection.find({},{'cgST': 1})
    all_clust_memb_cgmlst = _cluster_membership_collection.find({}, {'cgST': 1})

    cl_memb_cgst_list=[]
    st_cgst_list=[]
    for doc in all_clust_memb_cgmlst:
        cl_memb_cgst_list.append(doc["cgST"])
    for doc in all_st_cgmlst:
        st_cgst_list.append(doc["cgST"])


    faulty_cgst = [x for x in cl_memb_cgst_list if x not in st_cgst_list]

    for i in faulty_cgst:
        _cluster_membership_collection.delete_one(({"cgST": i}))