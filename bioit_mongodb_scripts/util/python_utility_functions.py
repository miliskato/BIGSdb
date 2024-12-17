import inspect
import logging
import smtplib
import socket
import sys
from copy import deepcopy
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import MONGO_CONFIG
from bioit_mongodb_scripts.model.json_model import MongoRecordDict


def get_mongodb_config_data() -> Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]:
    """
    Reads the global bigsdb config
    :return:
    """
    with Path(MONGO_CONFIG).open('r') as handle:
        mongo_config_data = yaml.safe_load(handle)
    return mongo_config_data

def is_viral(species:str) -> bool:
    """
    Check if the current specie is viral
    :param species: species to evaluate
    :return: True if specie is viral
    """
    mongo_config=get_mongodb_config_data()
    return species in mongo_config['viral_species']

def load_config(config: Path) -> Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]:
    """
    Loads a config file.
    :param config: path to the config file
    :return: the config file as a dictionary
    """
    with config.open() as handle:
        config_data = yaml.safe_load(handle)
    return config_data


def send_email(content: str, subject=None,
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
        message['Subject'] = subject if subject is not None else \
            f"{Path((inspect.stack()[1]).filename).name} fail on host {socket.gethostname()}"
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


def merge_mongo_dicts(target_dict: MongoRecordDict, merging_dict: MongoRecordDict) -> None:
    """merge a MongoRecordDict into another MongoRecordDict"""
    _merge_nested_dicts(target_dict, merging_dict)


def _merge_nested_dicts(target_dict: Union[MongoRecordDict,Dict], merging_dict: [MongoRecordDict,Dict]) -> Dict:
    """
    Merges a nested dictionary into another target nested dictionary, seeing as this does not create a deepcopy,
    changes are applied regardless of if the output is captured
    :param target_dict: dictionary to be merged in
    :param merging_dict: dictionary to merge into target
    :return: merged target directory
    """
    for key, value in merging_dict.items():
        if key in target_dict and isinstance(target_dict[key], dict) and isinstance(value, dict):
            _merge_nested_dicts(target_dict[key], value)
        else:
            target_dict[key] = value
    return target_dict


def access_value_in_dict_using_list_as_dictpath(dict_path: List, search_dict: Dict[str, Any]) -> Optional[str]:
    """
    Given a dictionary path as a list of ordered subkeys, gets the value of this dictionary path from the given search
    dictionary.
    :param dict_path: ordered list of the path in the dictionary
    :param search_dict: The dictionary in which to search for the dict_path
    :return: str or None
    """
    current = deepcopy(search_dict)
    for key in dict_path:
        current = current.get(key)
        if not current:
            break
    return current
