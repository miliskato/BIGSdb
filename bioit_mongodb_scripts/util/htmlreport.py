from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup, Tag


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

    def find_report_sections_by_header(self, header_texts: list[str]) -> list[Optional[Tag]]:
        """
        Finds a section of the report by using the header text.
        :param header_texts: list of the header texts that have to be found
        :return: either a  list of (a) Tag object(s) (if a matching section is found) or an empty list (if no matching
        section is found)
        """
        target_sections = self.soup.find_all('div', {"class": "report_section"})
        matching_sections = []

        for section in target_sections:
            # Check h2 and h3 for exact matches
            h2_match = section.h2 and section.h2.text in header_texts
            h3_match = section.h3 and section.h3.text in header_texts

            # Check p tags for text that starts with any of the header texts
            p_match = any(section.p and section.p.text.startswith(header) for header in header_texts)

            if h2_match or h3_match or p_match:
                matching_sections.append(section)

        return matching_sections

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
        :param file: Path to the output file
        :return: None
        """
        with file.open('w') as handle:
            handle.write(str(self.soup))
