import logging
import smtplib
import socket
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import MONGO_CONFIG


def get_mongodb_config_data() -> Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]:
    """
    Reads the global bigsdb config
    :return:
    """
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        mongo_config_data = yaml.safe_load(handle)
    return mongo_config_data


def send_email(content: str, subject: str = f"{Path(__file__).name} fail on host {socket.gethostname()}",
               config: Dict[str, str] = get_mongodb_config_data().get('mail'), dont_send_email: bool = False) -> None:
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
        message['Subject'] = subject
        message['From'] = config['from']
        message['To'] = config['to']
        message.set_content(content)
        with smtplib.SMTP(config['host']) as s:
            s.send_message(message)
    logging.debug(content)


def convert_dmyhms_to_ymd(datetimestring: str) -> str:
    """
    Converts long custom Camel format to short datetime string format
    :param datetimestring: datetimestring in dmyhms format
    :return: Short datetime string format (ymd)
    """
    return datetime.strptime(datetimestring, '%d/%m/%Y - %X').strftime('%Y-%m-%d')

def convert_ymd_to_dmyhms(datetimestring: str) -> str:
    """
    Revert SQL or other YMD to Camel's custom datetime notation
    :param datetimestring: datetime string in '%Y-%m-%d'
    :return: datetime string in '%d/%m/%Y - %X'
    """
    return datetime.strptime(datetimestring, '%Y-%m-%d').strftime('%d/%m/%Y - %X')

def convert_dmyhms_to_dateobj(datetimestring: str) -> datetime.date:
    """
    return datetime object from Camel's custom datetime notation
    :param datetimestring: datetime sting in '%d/%m/%Y - %X' format
    :return: datetime.datetime object
    """
    return datetime.strptime(datetimestring, '%d/%m/%Y - %X').date()