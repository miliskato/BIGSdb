import json
import logging
import sys
import tempfile
from pathlib import Path

import paramiko

# Configure stdout logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

# SFTP connection parameters
hostname = 'hera-dc.healthdata.be'
port = 2222  # Default SFTP port
username = 'bioit_hera_test'
password = 'in keepass'

# Create an SSH client
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# todo discuss flow & on which VM
mapping_table = {'_id': 'test_mk', 'pseudo_id': 'test_mk'}  # todo remove dev
mapping_table_healthdata_names = {'TX_BUSINESS_KEY ': mapping_table['_id'],
                                  'TX_BIOIT_TECHNICAL_ID': mapping_table['pseudo_id']}
with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
    jsonfile = Path(temp_json_dir) / f"{mapping_table['_id']}.json"
    with jsonfile.open('w') as handle:
        handle.write(json.dumps(mapping_table_healthdata_names))
    try:
        # Connect to the server
        ssh.connect(hostname, port, username, password)

        # Create an SFTP session
        sftp = ssh.open_sftp()

        # Upload the file
        remote_path = f'upload/{jsonfile.name}'
        sftp.put(str(jsonfile), remote_path)  # todo add 'test' between upload folder and file?
        logging.info(f"File uploaded successfully to {remote_path}")

        # Close the SFTP session
        sftp.close()
    except Exception as exceptionmessage:  # todo except send email?
        logging.error(exceptionmessage)
    finally:
        # Close the SSH connection
        ssh.close()