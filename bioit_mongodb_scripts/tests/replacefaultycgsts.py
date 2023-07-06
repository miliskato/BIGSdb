import logging
import os
import smtplib
import socket
import sys
import traceback
from email.message import EmailMessage
from pathlib import Path
from typing import Dict

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

#from bioit_mongodb_scripts.mainmongo import MainMongo
#from bioit_mongodb_scripts.reanalysis.reanalysis_noslurm import reanalysis_noslurm
#from bioit_mongodb_scripts.reanalysis.reanalysis_triggers.reanalysis_triggers import reanalysis_triggers
#from bioit_mongodb_scripts.tempid_replacer import TempidReplacer
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

    all_cgmlst = _st_collection.find({},{'cgST': 1, 'cgMLST': 1})
    big_list = []
    for document in all_cgmlst:
        samecgsts = list(_st_collection.find({'cgMLST':document['cgMLST']}, {'cgST':1, '_id':0}))
        if len(samecgsts) > 1:
            sublist = [x['cgST'] for x in samecgsts]'_id' = {ObjectId} ObjectId('640849b3f1c40db9ab83b127')
            if sublist not in big_list:
                big_list.append(sublist)
    for list in big_list:
        for faulty_cgst in list[1:]:
            print('###faulty cgst', faulty_cgst, '###rigt cgst', list[0])
            _isolates_collection.update_one({"cgST": faulty_cgst}, {"$set": {"cgST": list[0]}})
            _st_collection.delete_one(({"cgST": faulty_cgst}))
            _cluster_membership_collection.delete_one(({"cgST": faulty_cgst}))
            _old_isolateresults_collection.update_one({"cgST": faulty_cgst}, {"$set": {"cgST": list[0]}})

