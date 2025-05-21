import inspect
import logging
import smtplib
import socket
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from bioit_bigsdb_scripts.components.psql import TblSchemes

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.config import BIGSDB_CONFIG


def get_bigsdb_config_data() -> Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]:
    """
    Reads the global bigsdb config
    :return:
    """
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config_data = yaml.safe_load(handle)
    return bigsdb_config_data


def send_email(content: str, subject=None,
               config: Dict[str, str] = get_bigsdb_config_data().get('mail'),
               dont_send_email: bool = False) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :param config: config containing mail dict
    :param dont_send_email: do not send emails, only log
    :return: None
    """
    if not dont_send_email:
        message = EmailMessage()
        message['Subject'] = subject if subject is not None else f"{Path((inspect.stack()[1]).filename).name} fail on host {socket.gethostname()}"
        message['From'] = config['from']
        message['To'] = config['to']
        message.set_content(content)
        with smtplib.SMTP(config['host']) as s:
            s.send_message(message)
    logging.debug(content)


def get_cgmlst_bigsdb_scheme_id(species: str) -> int:
    """
    Returns the cgMLST BIGSdb scheme id for a specific species:
    :param species: commonly used bioit species name: either genus or specific like stec
    :return: cgMLST BIGSdb scheme id
    """
    with TblSchemes(species, 'isolates') as isolates_schemes_psql_tbl:
        cgmlst_bigsdb_scheme_id = isolates_schemes_psql_tbl.select_scheme_id_cgmlst()[0][0]
    return cgmlst_bigsdb_scheme_id
