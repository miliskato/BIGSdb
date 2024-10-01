import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import paramiko


def send_dictionary_to_ods_or_dwh(pseudo_id: str, ods_or_dwh: str, dictionary_to_send: Dict[str, Any],
                                  sftp: paramiko.SFTPClient, alternate_dtap: Optional[str] = None):
    """
    Sends a dictionary to DWH or ODS, should be respectively the genomic indicators or the mapping table.
    :param pseudo_id: psuedonymized id to give as a filename
    :param ods_or_dwh: 'ODS' or 'DWH'
    :param dictionary_to_send: sendable dictionary; mapping table for ODS and genomic indicators for DWH
    :param sftp: Paramiko sftp client element to send the dictionary to
    :param alternate_dtap: 'dev', 'test' or 'acc' if/when needed
    :return: None
    """
    with tempfile.TemporaryDirectory(dir='/tmp') as temp_json_dir:

        # create temporary json file to upload
        # business key is not allowed to be in the filename according to Sébastien Pendeville
        jsonfile = Path(temp_json_dir) / f"{pseudo_id}.json"
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
