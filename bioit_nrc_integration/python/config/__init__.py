import yaml
from pathlib import Path

_config_folder = Path(__file__).resolve().parent

SFTP_CREDENTIALS_HD = _config_folder / 'sftp_credentials.yml'
CODES_GENOMIC_ODS = _config_folder / 'codes_send_genomic_to_ODS.yml'
CODES_NOMINATIVE_ODS = _config_folder / 'codes_get_nominative_from_ODS.yml'
