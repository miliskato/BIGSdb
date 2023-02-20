import argparse
import subprocess
import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data

# This script currently expects the dir to have the sample name, and to contain report.txt, report.html and the report directory.
bigsdb_config_data = get_bigsdb_config_data()
argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--reportdirectory', required=True, type=str)
argument_parser.add_argument('--species', required=True, type=str, choices=list(get_bigsdb_config_data()['species']))
args = argument_parser.parse_args()
reportdirectory = args.reportdirectory
species = args.species

if not reportdirectory.endswith('/'):
    samplename = reportdirectory.split('/')[-1]
elif reportdirectory.endswith('/'):
    samplename = reportdirectory.split('/')[-2]
    reportdirectory = reportdirectory[0:-1]
print(samplename)

bashCommand = f"sudo mv {reportdirectory} /reports/{species}/"
print(bashCommand)
process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
output, error = process.communicate()

# # Symlinks happen automatically now I think
# bashCommand = f"sudo ln -s /reports/{species}/{samplename} /var/www/html/galaxyreports/{species}/"
# print(bashCommand)
# process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
# output, error = process.communicate()
