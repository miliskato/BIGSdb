from pathlib import Path
from typing import Union

from bs4 import BeautifulSoup, Tag

from bioit_mongodb_scripts.reanalysis import PARSING_ARGUMENTS
from bioit_mongodb_scripts.util.python_utility_functions import load_config


class HtmlReport:
    """
    Class to handle the HTML report.
    """

    def __init__(self, html_path: Path) -> None:
        """
        Initializes this class.
        :param html_path: Path to the HTML file
        :return: None
        """
        self.html_path = html_path
        self.soup = self._load_html()

    def _load_html(self) -> BeautifulSoup:
        """
        Loads the html report into a BeautifulSoup object.
        :return: BeautifulSoup object
        """
        with self.html_path.open('r') as handle:
            soup = BeautifulSoup(handle, 'lxml')
        return soup

    def find_report_section_by_header(self, header_text: str) -> Union[Tag, None]:
        """
        Finds a section of the report by using the header text.
        :param header_text: header text that has to be found
        :return: either a Tag object (if a matching section is found) or None (if no matching section is found)
        """
        target_sections = self.soup.find_all('div', {"class": "report_section"})
        for section in target_sections:
            if (section.h2 and header_text == section.h2.text) or (section.h3 and header_text == section.h3.text):
                return section
            if section.p and section.p.text.startswith(header_text):
                return section

    def find_analysis_date(self) -> str:
        """
        Finds the analysis date in the BeautifulSoup object.
        :return: str, the analysis date
        """
        for row in self.soup.find_all('tr'):
            if row.find('td') and row.find('td').text.strip() == "Analysis date:":
                analysis_date = row.find_all('td')[1].text.strip()
                return analysis_date

    def add_anchor_tags(self, headers_names: dict[str, str]) -> None:
        """
        Adds anchor tags to the BeautifulSoup object.
        :param headers_names: dictionary with the headers as keys and the anchor names as values
        :return: None
        """
        headers = self.soup.find_all(["h3", "h2"])
        for header in headers:
            header_text = header.text.strip()
            if header_text in headers_names.keys():
                anchor_name = headers_names[header_text]
                if not self.soup.find('a', attrs={"name": anchor_name}):
                    anchor_tag = self.soup.new_tag("a", attrs={"name": anchor_name})
                    header.insert_before(anchor_tag)

    def save_file(self, file: Path) -> None:
        """
        Saves the BeautifulSoup object as a file.
        :param: Path to the output file
        :return: None
        """
        with file.open('w') as handle:
            handle.write(str(self.soup))
