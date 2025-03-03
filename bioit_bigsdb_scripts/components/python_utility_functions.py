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

class SpeciesTypingSchemeConfig:
    def __init__(self, data: Dict[str, Union[str, List[Any]]]):
        self.dirdb = data.get('dirdb')
        self.scheme_fields = data.get('scheme_fields')
        self.bigsdb_scheme_name = data.get('bigsdb_scheme_name')

class SpeciesGeneDetectionSchemeConfig:
    def __init__(self, data: Dict[str, Union[str, List[Any]]]):
        self.metadata_file = data.get('metadatafile')
        self.bigsdb_scheme_name = data.get('schemename_bigsdb')
        self.html_scheme_anchor = data.get('schemename_html')


class JsonGeneDetectionSchemeConfig:
    def __init__(self, data: Dict[str, str]):
        self.metadata_file = data.get('metadatafile')
        self.bigsdb_scheme_name = data.get('schemename_bigsdb')
        self.html_scheme_anchor = data.get('schemename_html')

class SpeciesJsonConfig:
    def __init__(self, data: Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]):
        self.typing_schemes: Dict[str,str] = {}
        try:
            for key, value in data.get('typing_schemes', {}).items():
                self.typing_schemes[key] = value.get('type')
        except:
            pass

        self.genedetection_schemes: Dict[str, JsonGeneDetectionSchemeConfig] = {}
        try:
            for key, value in data.get('genedetection_schemes').items():
                self.genedetection_schemes[key] = JsonGeneDetectionSchemeConfig(value)
        except:
            pass

class SpeciesConfig:
    def __init__(self, data: Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]):
        self.typing_schemes: Dict[str, SpeciesTypingSchemeConfig] = {}
        for key, value in data.get['typing_schemes'].items():
            self.typing_schemes[key] = SpeciesTypingSchemeConfig(value)

        self.genedetection_schemes: Dict[str, SpeciesGeneDetectionSchemeConfig] = {}
        for key, value in data['genedetection_schemes'].items():
            self.genedetection_schemes[key] = SpeciesGeneDetectionSchemeConfig(value)

class Config:
    def __init__(self, data: Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]):
        self.data = data

        self.config_species : Dict[str, SpeciesConfig] = {}
        self.config_species_json : Dict[str, SpeciesJsonConfig] = {}
        for key, value in data['species_json'].items():
         self.config_species_json[key] = SpeciesJsonConfig(value)







def get_bigsdb_config_data() -> Dict[str, Union[str, List[Any], Dict[str, Union[str, Dict[str, Any]]]]]:
    """
    Reads the global bigsdb config
    :return:
    """
    with open(BIGSDB_CONFIG, encoding='utf-8') as handle:
        bigsdb_config_data = yaml.safe_load(handle)
    return bigsdb_config_data

def get_bigsdb_config() -> Config:
    bigsdb_config_data = get_bigsdb_config_data()
    return Config(bigsdb_config_data)

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

if __name__ == '__main__':
    config = get_bigsdb_config()
    print(config)