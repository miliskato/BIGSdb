import os
import yaml
_config_folder = os.path.dirname(os.path.realpath(__file__))

MONGO_CONFIG = os.path.join(_config_folder, 'config.yml')
HIERCC_CONFIG = os.path.join(_config_folder, 'hiercc_config.yml')

with open(HIERCC_CONFIG) as handle:
    HIERCC_CONFIG = yaml.load(handle, Loader=yaml.SafeLoader)