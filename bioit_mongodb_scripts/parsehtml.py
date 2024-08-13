#!/usr/bin/env python
import argparse
import sys
from pathlib import Path
from typing import List, Union

import yaml
from bs4 import BeautifulSoup, Tag

from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str, choices=specieslist)
    parser.add_argument("--html1", required=True, type=Path)
    parser.add_argument("--html2", required=True, type=Path)
    parser.add_argument("--analysis-arguments", required=True, nargs='+', type=str)
    parser.add_argument("--new-file", required=True, type=Path)
    return parser.parse_args()


class ParseHtml:
    """
    Parses the old and new html report and replaces the sections that changed with regard to the old report.
    """
    def __init__(self, html1: Path, html2: Path, analysis_arguments: List[str], species: str, new_file: Path) -> None:
        """
        Initializes this class and executes the main function.
        :param html1: Path to the first html report
        :param html2: Path to the second html report
        :param analysis_arguments: analysis arguments
        :param species: commonly used bioit species name: either genus or specific like stec
        :param new_file: Path to the new html report
        :return: None
        """
        self._html1 = html1
        self._html2 = html2
        self._analysis_arguments = analysis_arguments
        self._species = species
        self._new_file = new_file
        self._adapt_html()

    def _adapt_html(self) -> None:
        """
        Adapts the html report.
        :return: None
        """
        soup1 = self.__load_html(self._html1)
        soup2 = self.__load_html(self._html2)
        new_arguments = self.__change_arguments()
        for analysis_argument in new_arguments:
            soup1 = self.__replace_section(soup1, soup2, analysis_argument)
        with open(self._new_file, 'w', encoding='utf-8') as file:
            file.write(str(soup1))

    @staticmethod
    def __load_html(filename: Path) -> BeautifulSoup:
        """
        Loads the html report into a BeautifulSoup object.
        :param filename: Path to the file that has to be loaded
        :return: BeautifulSoup object
        """
        with open(filename, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'lxml')
        return soup

    def __change_arguments(self) -> List[str]:
        """
        Changes the arguments into the strings used in the header of the report.
        :return: list of the changed arguments
        """
        new_arguments = []
        with Path('arguments.yml').open('r') as handle:
            codes_dict = yaml.safe_load(handle)
            if self._species in codes_dict:
                for analysis_argument in self._analysis_arguments:
                    if analysis_argument in codes_dict[self._species]:
                        value = codes_dict[self._species][analysis_argument]
                        if isinstance(value, list):
                            new_arguments.extend(value)
                        else:
                            new_arguments.append(value)
        new_arguments.append('Input')
        return new_arguments

    def __replace_section(self, soup1: BeautifulSoup, soup2: BeautifulSoup, header_text: str) -> BeautifulSoup:
        """
        Replaces a section of the first BeautifulSoup object by a section of the second BeautifulSoup object.
        :param soup1: first BeautifulSoup object
        :param soup2: second BeautifulSoup object
        :return: the first BeautifulSoup object which contains the replaced section
        """
        section_to_replace = self.___find_section_by_header(soup1, header_text)
        new_section = self.___find_section_by_header(soup2, header_text)
        # Replace these section
        if section_to_replace and new_section:
            section_to_replace.replace_with(new_section)
        return soup1

    @staticmethod
    def ___find_section_by_header(soup: BeautifulSoup, header_text: str) -> Union[Tag, None]:
        """
        Finds a section of the report by using the header text.
        :param soup: BeautifulSoup object that has to be searched
        :param header_text: header text that has to be found
        :return: either a Tag object (if a matching section is found) or None (if no matching section is found)
        """
        target_sections = soup.find_all('div', {"class": "report_section"})
        for section in target_sections:
            if (section.h2 and header_text == section.h2.text) or (section.h3 and header_text == section.h3.text):
                return section
            if section.p and section.p.text.startswith(header_text):
                return section


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # Run main
    ParseHtml(args.html1,
              args.html2,
              args.analysis_arguments,
              args.species,
              args.new_file)
