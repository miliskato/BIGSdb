import inspect
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
        bigsdb_config_data = yaml.safe_load(handle)
    return bigsdb_config_data
