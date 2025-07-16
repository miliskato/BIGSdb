#!/usr/bin/env python
import argparse
import sys
from pathlib import Path
from typing import Optional

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.util.python_utility_functions import load_config
from bioit_mongodb_scripts.reanalysis import PARSING_ARGUMENTS
from bioit_mongodb_scripts.util.htmlreport import HtmlReport
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider


def parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--species", required=True, type=str, choices=MongoConfigProvider.get_currently_supported_species())
    parser.add_argument("--base-html", required=True, type=Path)
    parser.add_argument("--updated-html", required=True, type=Path)
    parser.add_argument("--analysis-arguments", required=True, nargs='+', type=str)
    parser.add_argument("--new-file", required=False, type=Path)
    return parser.parse_args()


class HtmlReplacer:
    """
    Parses the old and new HTML report and replaces the sections that changed with regard to the old report.
    """

    def __init__(self, base_html: Path, updated_html: Path, analysis_arguments: list[str], species: str,
                 new_file: Optional[Path]) -> None:
        """
        Initializes this class.
        :param base_html: Path to the base HTML report
        :param updated_html: Path to the updated HTML report
        :param analysis_arguments: analysis arguments
        :param species: commonly used bioit species name: either genus or specific like stec
        :param new_file: Path to the new html report
        :return: None
        """
        self._base_html = HtmlReport(base_html)
        self._updated_html = HtmlReport(updated_html)
        self._analysis_arguments = analysis_arguments
        self._species = species
        self._new_file = new_file if new_file else updated_html

    def adapt_html(self) -> None:
        """
        Adapts the html report.
        :return: None
        """
        new_arguments = self._convert_arguments_to_headers()
        for analysis_argument in new_arguments:
            self._replace_section(analysis_argument)
        self._replace_analysis_date()
        self._base_html.save_file(self._new_file)

    def _convert_arguments_to_headers(self) -> list[str]:
        """
        Changes the arguments into the strings used in the headers of the report.
        :return: list of the changed arguments
        """
        new_arguments = []
        codes_dict = load_config(PARSING_ARGUMENTS)
        if codes_dict.get(self._species):
            for analysis_argument in self._analysis_arguments:
                if analysis_argument in codes_dict[self._species]:
                    value = codes_dict[self._species][analysis_argument]
                    if isinstance(value, list):
                        new_arguments.extend(value)
                    else:
                        new_arguments.append(value)
        return new_arguments

    def _replace_section(self, header_text: str) -> None:
        """
        Replaces a section of the first BeautifulSoup object by a section of the second BeautifulSoup object.
        :param header_text: header text with which the section should be found
        :return: None
        """
        section_to_replace = self._base_html.find_report_section_by_header(header_text)
        new_section = self._updated_html.find_report_section_by_header(header_text)
        # Replace this section
        if section_to_replace and new_section:
            section_to_replace.replace_with(new_section)

    def _replace_analysis_date(self) -> None:
        """
        Replaces the analysis date in the base BeautifulSoup object by the analysis date of the updated BeautifulSoup
        object.
        :return: None
        """
        new_analysis_date = self._updated_html.find_analysis_date()
        for row in self._base_html.soup.find_all('tr'):
            if row.find('td') and row.find('td').text.strip() == "Analysis date:":
                row.find_all('td')[1].string = new_analysis_date
                break


if __name__ == '__main__':
    args = parse_arguments()

    # Run main
    html_replacer = HtmlReplacer(
        args.base_html,
        args.updated_html,
        args.analysis_arguments,
        args.species,
        args.new_file
    )
    html_replacer.adapt_html()
