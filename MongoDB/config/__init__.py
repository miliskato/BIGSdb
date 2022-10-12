import os
import yaml
_config_folder = os.path.dirname(os.path.realpath(__file__))

MONGO_CONFIG = os.path.join(_config_folder, 'config.yml')
