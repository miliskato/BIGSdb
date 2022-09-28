import subprocess
import argparse
import logging
import sys
import os
import yaml
import json
from pathlib import Path

from util.mongo_initialisation import Mongoinitialisation
from config import MONGO_CONFIG

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=['mycobacterium', 'listeria', 'neisseria', 'stec', 'salmonella'])
    argument_parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='/home/BIGSdb/3.9PythonVenv/bin/python3.9')
    return argument_parser.parse_args()


# def run_subprocess(custom_command):
#     result = subprocess.run(
#         custom_command,
#         stdout=sys.stdout,
#         stderr=sys.stderr,
#         shell=True,
#         executable='/bin/bash')
#     # if result.returncode != 0:
#     #     send_email(
#     #         f'Error handling output of automatic reanalysis pipeline on {args.species}, {isolate_id}',
#     #         f"look in file /reports/{args.species}/{temp_new_sample_name}/{temp_new_sample_name}.log",
#     #         config_data['mail'])

if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments()

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Open collections
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(config_data, args.species)

    source = os.path.dirname(__file__)
    parent = os.path.join(source, '../')

    for document in isolates_collection.find():
        jsonfile = f"{document['results']['isolates_id']}_temp.json"
        with open(f"{document['results']['isolates_id']}_temp.json", 'w') as handle:
            handle.write(json.dumps(document['results']))
        subprocess.call([f"{args.pyvenvpythonpath} {os.path.join(parent, 'bioit_custom_scripts/main_results_inserter.py')} --jsonfilepath {jsonfile} --species {args.species} --isolatename {document['results']['isolates_id']} --uploadermailadress michael"], shell=True)
        handle.close()
        os.remove(jsonfile)