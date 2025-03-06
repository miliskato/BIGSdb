#!/usr/bin/env python
import argparse
import sys
from os import fdopen, remove
from pathlib import Path
from shutil import move, copymode
from tempfile import mkstemp
from typing import List

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import TAGGER_CONFIG
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, load_config


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--htmlfilepath', required=True, type=Path)
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


class HtmlTagger:
    """
    Tags the html report.
    """
    def __init__(self, htmlfilepath: Path, species: str) -> None:
        """
        Initializes this class and executes the main function.
        :param htmlfilepath: path to the html file
        :param species: commonly used bioit species name: either genus or specific like stec
        """
        self._htmlfilepath = htmlfilepath
        self._species = species
        tagger_config = load_config(TAGGER_CONFIG)
        # Execute main function
        if tagger_config.get(self._species):
            for scheme in tagger_config[self._species]:
                self._tagger(tagger_config[self._species][scheme])

    def _tagger(self, html_name: str) -> None:
        """
        This function tags a html file at specific locations (scheme start). These tags can then be used to direct the
        user to that exact location in bigsdb.
        :param html_name: name of the scheme to be tagged in the html file
        :return: None
        """
        htmlreport = ''.join(['<div class="report_section"><h3>', html_name, '</h3>'])
        htmltag = ''.join(['<a name="', html_name, '"></a>'])
        # Create temp file
        fh, abs_path = mkstemp()
        with fdopen(fh, 'w') as new_file:
            with open(self._htmlfilepath) as old_file:
                for line in old_file:
                    new_file.write(line.replace(''.join([htmltag, htmlreport]), htmlreport).replace(
                        htmlreport, ''.join([htmltag, htmlreport])))
        # Copy the file permissions from the old file to the new file
        copymode(self._htmlfilepath, abs_path)
        # Remove original file
        remove(self._htmlfilepath)
        # Move new file
        move(abs_path, self._htmlfilepath)


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # Run main
    HtmlTagger(args.htmlfilepath, args.species)
