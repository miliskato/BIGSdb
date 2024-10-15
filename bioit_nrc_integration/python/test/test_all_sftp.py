import json
import logging
import sys
from pathlib import Path

import paramiko
import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.mainmongo import MainMongo
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data
from bioit_nrc_integration.python.config import SFTP_CREDENTIALS_HD
from bioit_nrc_integration.python.error_checker_for_main_sender_to_HD import ErrorCheckerForMainSenderToHD
from bioit_nrc_integration.python.get_nominative_from_ODS import MainNominativeDataParserFromOds
from bioit_nrc_integration.python.main_sender_to_HD import MainSenderToHD
from bioit_nrc_integration.python.test.testfiles import testfiles_folder, TESTFILES

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

with TESTFILES.open('r') as handle:
    testfiles_dict = yaml.safe_load(handle)
# get sftp credentials
with SFTP_CREDENTIALS_HD.open('r') as handle:
    sftp_credentials_hd = yaml.safe_load(handle)

# get mongodb config data
mongo_config_data = get_mongodb_config_data()

DTAP = 'dev'  # should only be dev or acc

for species, species_testfiles in testfiles_dict.items():
    mongoinit_azure = MongoInitialisation(species, mongo_config_data=mongo_config_data,
                                          selected_connection_string='CONNECTION_STRING_AZURE',
                                          alternate_dtap=DTAP)
    isolates_collection, old_isolateresults_collection, isolates_badqc_collection, \
        isolates_resequencing_collection = mongoinit_azure.initialise_collections()

    mongoinit_local = MongoInitialisation(species, mongo_config_data=mongo_config_data,
                                          selected_connection_string='CONNECTION_STRING_LOCAL',
                                          alternate_dtap=DTAP)
    mapping_table_collection = mongoinit_local.initialise_mapping_table_collection()

    """
    Upload CLIN and LAB files to ODS sftp. 
    """
    # Create an SSH client
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Connect to the server
    ssh.connect(sftp_credentials_hd['hostname_get_nominative_from_ODS'],
                sftp_credentials_hd['port_get_nominative_from_ODS'],
                sftp_credentials_hd['username_get_nominative_from_ODS'],
                sftp_credentials_hd['password_get_nominative_from_ODS'])
    # Create an SFTP session
    sftp = ssh.open_sftp()
    sftp.put(str(testfiles_folder / species_testfiles['get_nominative_from_ODS_CLIN']),
             f"upload/{DTAP}/test_dummy_{species}_CLIN_.json")
    sftp.put(str(testfiles_folder / species_testfiles['get_nominative_from_ODS_LAB']),
             f"upload/{DTAP}/test_dummy_{species}_LAB_.json")

    """
    Run Nominative data parser on CLIN and LAB files uploaded to ODS
    """
    MainNominativeDataParserFromOds(test_dummy=True, alternate_dtap=DTAP)

    """
    After successful parsing the file is moved to the processed folder, remove it from there to clean up.
    """
    sftp.remove(f"upload/{DTAP}/processed/test_dummy_{species}_CLIN_.json")
    sftp.remove(f"upload/{DTAP}/processed/test_dummy_{species}_LAB_.json")
    sftp.close()
    ssh.close()

    """
    Insert dummy genomic report JSON into remote isolates collection, skip MainMongo. 
    Use 'validated' = true value to mimic validation
    """
    with (testfiles_folder / species_testfiles['genomic_json_report']).open('r') as handle:
        dummy_genomic_report = json.load(handle)
        dummy_genomic_report['validation'] = {'outcome': 'good'}
    isolates_collection.insert_one(dummy_genomic_report)

    """
    Insert mapping table for the main sender to be able to discover and send it.
    """
    with (testfiles_folder / species_testfiles['mapping_table']).open('r') as handle:
        dummy_mapping_table = json.load(handle)
    mapping_table_collection.insert_one(dummy_mapping_table)

    """
    Run main sender
    """
    MainSenderToHD(test_dummy=True, alternate_dtap=DTAP)

    """
    Move ODS & DWH files to processed folder as if HD had done it
    """
    # Create an SSH client
    ssh_ods = paramiko.SSHClient()
    ssh_ods.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Connect to the server
    ssh_ods.connect(sftp_credentials_hd['hostname_send_mapping_table_to_ODS'],
                    sftp_credentials_hd['port_send_mapping_table_to_ODS'],
                    sftp_credentials_hd['username_send_mapping_table_to_ODS'],
                    sftp_credentials_hd['password_send_mapping_table_to_ODS'])
    # Create an SFTP session
    sftp_ods = ssh_ods.open_sftp()
    
    sftp_ods.rename(f"upload/{DTAP}/{dummy_mapping_table['pseudo_id']}.json",
                    f"upload/{DTAP}/processed/{dummy_mapping_table['pseudo_id']}.json")
    sftp_ods.close()
    ssh_ods.close()

    # Create an SSH client
    ssh_dwh = paramiko.SSHClient()
    ssh_dwh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Connect to the server
    ssh_dwh.connect(sftp_credentials_hd['hostname_send_genomic_to_DWH'],
                    sftp_credentials_hd['port_send_genomic_to_DWH'],
                    sftp_credentials_hd['username_send_genomic_to_DWH'],
                    sftp_credentials_hd['password_send_genomic_to_DWH'])
    # Create an SFTP session
    sftp_dwh = ssh_dwh.open_sftp()

    sftp_dwh.rename(f"to_hd/{DTAP}/{dummy_mapping_table['pseudo_id']}.json",
                    f"to_hd/{DTAP}/processed/{dummy_mapping_table['pseudo_id']}.json")

    sftp_dwh.close()
    ssh_dwh.close()
    
    """
    Run main error checker and processed acknowledger
    """
    ErrorCheckerForMainSenderToHD(test_dummy=True, alternate_dtap=DTAP)

    """
    Run MainMongo for reanalysis
    """
    MainMongo(dummy_genomic_report['_id'], 'salmonella', 'reanalysis', pipeline_hash='0123456789', jsonfilepath=testfiles_folder / species_testfiles['genomic_json_reanalysis_report'], alternate_dtap=DTAP)

    """
    Run main sender after reanalysis
    """
    MainSenderToHD(test_dummy=True, alternate_dtap=DTAP)

    """
    Move DWH files to processed folder as if HD had done it again
    """
    # Create an SSH client
    ssh_dwh = paramiko.SSHClient()
    ssh_dwh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # Connect to the server
    ssh_dwh.connect(sftp_credentials_hd['hostname_send_genomic_to_DWH'],
                    sftp_credentials_hd['port_send_genomic_to_DWH'],
                    sftp_credentials_hd['username_send_genomic_to_DWH'],
                    sftp_credentials_hd['password_send_genomic_to_DWH'])
    # Create an SFTP session
    sftp_dwh = ssh_dwh.open_sftp()

    sftp_dwh.rename(f"to_hd/{DTAP}/{dummy_mapping_table['pseudo_id']}.json",
                    f"to_hd/{DTAP}/processed/{dummy_mapping_table['pseudo_id']}.json")

    sftp_dwh.close()
    ssh_dwh.close()

    """
    Run main error checker and processed acknowledger again after reanalysis resending
    """
    ErrorCheckerForMainSenderToHD(test_dummy=True, alternate_dtap=DTAP)

    """
    Clean up both MongoDBs
    """
    # MongoDB Azure
    isolates_collection.delete_one({'_id': dummy_genomic_report['_id']})  # id = pseudo_id
    old_isolateresults_collection.delete_one({'isolates_id': dummy_genomic_report['_id']})  # id = pseudo_id

    # MongoDB local
    mapping_table_collection.delete_one({'_id': dummy_mapping_table['_id']})  # id = id

    nominative_labtest_clinical_metadata_collection = mongoinit_local.initialise_nominative_labtest_clinical_metadata_collection()
    unprocessed_nominative_labtest_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_labtest_metadata_collection()
    unprocessed_nominative_clinical_metadata_collection = mongoinit_local.initialise_unprocessed_nominative_clinical_metadata_collection()

    nominative_labtest_clinical_metadata_collection.delete_one({'_id': dummy_mapping_table['TX_BUSINESS_KEY']})
    unprocessed_nominative_labtest_metadata_collection.delete_one({'_id': dummy_mapping_table['TX_BUSINESS_KEY']})
    unprocessed_nominative_clinical_metadata_collection.delete_one({'_id': dummy_mapping_table['TX_BUSINESS_KEY']})
