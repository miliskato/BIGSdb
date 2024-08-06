import argparse
from pathlib import Path
from typing import List

import yaml
from bs4 import BeautifulSoup

from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


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

    def __init__(self, html1: Path, html2: Path, analysis_arguments: list, species: str, new_file: Path):
        self._html1 = html1
        self._html2 = html2
        self._analysis_arguments = analysis_arguments
        self._species = species
        self._new_file = new_file
        self._adapt_html()

    def __change_arguments(self):
        new_arguments = []
        for analysis_argument in self._analysis_arguments:
            with Path('arguments.yml').open('r') as handle:
                codes_dict = yaml.safe_load(handle)
                if codes_dict[self._species].get(analysis_argument):
                    new_arguments.append(codes_dict[self._species][analysis_argument])
        new_arguments.append('input')
        return new_arguments

    @staticmethod
    def __load_html(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file, 'lxml')
        return soup

    # Function to find a section by header text, traversing up the DOM tree to find the container div
    @staticmethod
    def ___find_section_by_header(soup, header_text):
        target_sections = soup.find_all('div', {"class": "report_section"})
        for section in target_sections:
            # print(section)
            if (section.h2 and header_text == section.h2.text) or (section.h3 and header_text == section.h3.text):
                return section

    def __replace_section(self, soup1, soup2, header_text):
        section_to_replace = self.___find_section_by_header(soup1, header_text)
        new_section = self.___find_section_by_header(soup2, header_text)
        # Replace these section
        if section_to_replace and new_section:
            section_to_replace.replace_with(new_section)
        return soup1

    def _adapt_html(self):
        soup1 = self.__load_html(self._html1)
        soup2 = self.__load_html(self._html2)
        new_arguments = self.__change_arguments()
        for analysis_argument in new_arguments:
            soup1 = self.__replace_section(soup1, soup2, analysis_argument)
        with open(self._new_file, 'w', encoding='utf-8') as file:
            file.write(str(soup1))


if __name__ == '__main__':
    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    ParseHtml(args.html1,
              args.html2,
              args.analysis_arguments,
              args.species,
              args.new_file)

