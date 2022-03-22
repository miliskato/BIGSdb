# This script currently expects the dir to have the sample name, and to contain report.txt, report.html and the report directory.

import argparse
from pathlib import Path
import subprocess

argument_parser = argparse.ArgumentParser()
argument_parser.add_argument('--reportdirectory', required=True, type=str)
argument_parser.add_argument('--species', required=True, type=str, choices=['mycobacterium', 'listeria'])
args = argument_parser.parse_args()
reportdirectory = args.reportdirectory
species = args.species

if not reportdirectory.endswith('/'):
    samplename = reportdirectory.split('/')[-1]
elif reportdirectory.endswith('/'):
    samplename = reportdirectory.split('/')[-2]
    reportdirectory = reportdirectory[0:-2]
print(samplename)

bashCommand = f"sudo mv {reportdirectory} /reports/{species}/"
print(bashCommand)
process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
output, error = process.communicate()

bashCommand = f"sudo ln -s /reports/{species}/{samplename} /var/www/html/galaxyreports/{species}/"
print(bashCommand)
process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
output, error = process.communicate()