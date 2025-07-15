#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import TAGGER_CONFIG
from bioit_mongodb_scripts.util.python_utility_functions import load_config
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.htmlreport import HtmlReport


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--html-path', required=True, type=Path)
    argument_parser.add_argument('--species', required=True, type=str, choices=MongoConfigProvider.get_currently_supported_species())
    return argument_parser.parse_args()


if __name__ == '__main__':
    # Parse arguments
    args = parse_arguments()

    # Run main
    html_tagger = HtmlReport(args.html_path)
    headers_names = load_config(TAGGER_CONFIG).get(args.species)
    if headers_names:
        html_tagger.add_anchor_tags(headers_names)
        html_tagger.save_file(args.html_path)
