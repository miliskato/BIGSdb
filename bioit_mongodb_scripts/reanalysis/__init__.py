from pathlib import Path

_config_folder = Path(__file__).resolve().parent

MONGO_REANALYSIS_CONFIG = _config_folder / 'config.yml'
