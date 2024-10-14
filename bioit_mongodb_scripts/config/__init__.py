import yaml
from pathlib import Path

_config_folder = Path(__file__).resolve().parent

MONGO_CONFIG = _config_folder / 'config.yml'
CLUSTERING_CONFIG = _config_folder / 'clustering_config.yml'
TAGGER_CONFIG = _config_folder / 'tagger_config.yml'

with open(CLUSTERING_CONFIG) as handle:
    CLUSTERING_CONFIG = yaml.load(handle, Loader=yaml.SafeLoader)
