import os
import yaml
_config_folder = os.path.dirname(os.path.realpath(__file__))

MONGO_CONFIG = os.path.join(_config_folder, 'config.yml')
CLUSTERING_CONFIG = os.path.join(_config_folder, 'clustering_config.yml')

with open(CLUSTERING_CONFIG) as handle:
    CLUSTERING_CONFIG = yaml.load(handle, Loader=yaml.SafeLoader)