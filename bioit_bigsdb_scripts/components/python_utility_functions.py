import logging
import smtplib
import socket
import sys
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.config import BIGSDB_CONFIG


def get_bigsdb_config_data() -> Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]:
    """
    Reads the global bigsdb config
    :return:
    """
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)
    return config_data


def send_email(content: str, subject: str = f"{Path(__file__).name} fail on host {socket.gethostname()}",
               config: Dict[str, str] = get_bigsdb_config_data().get('mail')) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :param config: config containing mail dict
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)
    logging.debug(content)
