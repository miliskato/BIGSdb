import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import paramiko


def send_dictionary_to_ods_or_dwh(ods_or_dwh: str, dictionary_to_send: Dict[str, Any],
                                  sftp: paramiko.SFTPClient, alternate_dtap: Optional[str] = None):
    """
    Sends a dictionary to DWH or ODS, should be respectively the genomic indicators or the mapping table.
    :param ods_or_dwh: 'ODS' or 'DWH'
    :param dictionary_to_send: sendable dictionary; mapping table for ODS and genomic indicators for DWH,
    should contain the pseudo_id as ['data']['TX_BIOIT_TECHNICAL_ID']
    :param sftp: Paramiko sftp client element to send the dictionary to
    :param alternate_dtap: 'dev', 'test' or 'acc' if/when needed:
    The ODS provided two sftp credentials; one for test & one for prod, the DWH only
    provided credentials for prod.
    the root folder in every sftp environment is the drop off location for the cycle for which it is meant.
    in order to tackle being able to test dev, test, and acc, all of these are created as separate folders
    in the DWH location.
    For the ODS, dev and acc folders are created in devtest and accprod respectively.
    :return: None
    """
    with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:

        # create temporary json file to upload
        # business key is not allowed to be in the filename according to Sébastien Pendeville
        jsonfile = Path(temp_json_dir) / f"{dictionary_to_send['data']['TX_BIOIT_TECHNICAL_ID']}.json"
        with jsonfile.open('w') as handle:
            handle.write(json.dumps(dictionary_to_send))

        # Set remote path
        if ods_or_dwh == 'ODS':
            remote_path = 'upload/'
        else:  # ods_or_dwh == 'DWH'
            remote_path = 'to_hd/'
        remote_path += f"{(alternate_dtap + '/') if alternate_dtap else ''}{jsonfile.name}"

        # Upload the file
        sftp.put(str(jsonfile), remote_path)
        logging.info(f"File uploaded successfully to {remote_path}")
