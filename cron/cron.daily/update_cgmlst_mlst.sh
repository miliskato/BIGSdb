#!/bin/bash

#add new alleles, loci and clustering informations
/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/MongoDB/new_alleles_profile_clustering_from_mongo_to_bigs.py
#replace new alleles by actual alleles in bigsdb
/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/MongoDB/hash_replacer.py
#update the regular database of loci alleles and schemes profiles
/home/BIGSdb/3.9PythonVenv/bin/python3.9  /home/BIGSdb/bioit_custom_scripts/Typing_alleles_intopsql.py
/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/Typing_loci_intopsql.py
/home/BIGSdb/3.9PythonVenv/bin/python3.9 /home/BIGSdb/bioit_custom_scripts/Typing_schemeprofiles_intopsql.py
