import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict

import paramiko


def send_dictionary_to_ods(dictionary_to_send: Dict[str, Any], sftp: paramiko.SFTPClient, upload_path: str):
    """
    Sends a dictionary to the ODS.
    :param dictionary_to_send: dictionary to send
    should contain the _id as ['data']['TX_LAB_SAMPLE_VAL']
    :param sftp: Paramiko sftp client element to send the dictionary to
    :param upload_path: the upload path
    The ODS provided two sftp credentials; one for test & one for prod.
    the root folder in every sftp environment is the drop off location for the cycle for which it is meant.
    For the ODS, dev and acc folders are created in devtest and accprod respectively.
    :return: None
    """
    with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:
        # create temporary json file to upload
        # business key is not allowed to be in the filename according to Sébastien Pendeville
        jsonfile = Path(temp_json_dir) / f"{dictionary_to_send['data']['TX_LAB_SAMPLE_VAL']}.json"
        with jsonfile.open('w') as handle:
            handle.write(json.dumps(dictionary_to_send))

        remote_path = f'{upload_path}{jsonfile.name}'

        # Upload the file
        sftp.put(str(jsonfile), remote_path)
        logging.info(f"File uploaded successfully to {remote_path}")
