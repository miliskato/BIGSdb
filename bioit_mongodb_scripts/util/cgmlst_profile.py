import datetime
from typing import Dict, List, Union


class cgMLSTProfile:
    """
    Class used to store cgMLST profiles  and sequence type and export them into convenient formats.
    """
    def __init__(self, data: List[Union[str, int]], headers: List[str] = None) -> None:
        """
        Initialize the class
        :param data: the st + cgmlst in a list (query from querymongo by assay and id)
        :param headers: the headers from the data (query from querymongo by assay and id also)
        :return: None
        """
        self.st = data[0]
        self.cgmlst = data[1:len(data)]
        if headers:
            self.loci = headers[1:len(headers)]

    def get_st_collection_entry(self) -> Dict[str, Union[str, int, object]]:
        """
        Creates a dict containing the sequence type and the cgmlst profile to enter into the sequence type collection
        :return: Dictionary containing the cgST, the cgmlst allele designations list and the current date
        """
        return {'cgST': int(self.st), 'cgMLST': self.cgmlst, 'insertion_date': datetime.datetime.utcnow()}
