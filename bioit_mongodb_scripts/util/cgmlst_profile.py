import datetime
from datetime import timezone
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
        self.st = None
        self.cgmlst = data[1:len(data)]
        if headers:
            self.loci = headers[1:len(headers)]

    def get_st_collection_entry(self) -> Dict[str, Union[str, int, object]]:
        """
        Creates a dict containing the sequence type and the cgmlst profile to enter into the sequence type collection
        :return: Dictionary containing the cgST, the cgmlst allele designations list, the current date, the status of
        insertion in bigsdb and a field used to capture for insertion only cgST wearing alleles already inserted in bigsdb
        """
        return {'cgST': int(self.st), 'cgMLST': self.cgmlst, 'insertion_date': datetime.datetime.now(timezone.utc), 'bigsdb_status': 'pending', 'select_for_bigsdb_insertion': False}
