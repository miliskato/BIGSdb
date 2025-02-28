#!/usr/bin/env python
import argparse
import sys
from os import fdopen, remove
from pathlib import Path
from shutil import move, copymode

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import TAGGER_CONFIG
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, load_config
from bioit_mongodb_scripts.util_azure.htmlreport import HtmlReport


def parse_arguments(specieslist: list[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--html-path', required=True, type=Path)
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # Run main
    html_tagger = HtmlReport(args.html_path)
    headers_names = load_config(TAGGER_CONFIG).get(args.species)
    html_tagger.add_anchor_tags(headers_names)
    html_tagger.save_file(args.html_path)
