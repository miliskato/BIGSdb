#!/bin/bash
#If new uploads are validated for metadata in the submission table of isolate DB, this cron job will insert them into BIGSdb
#The cronjob is deployed using ansible in the bigsdb role (tasks/main.yml)
# */2 *   * * *   bigsdb    bash /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/cron_startinsertion_lab_metadata.sh

/home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9 /home/bigsdb/BIGSdb/bioit_bigsdb_scripts/components/metadata_insertion_from_bigs.py --species to_be_replaced_by_ansible
