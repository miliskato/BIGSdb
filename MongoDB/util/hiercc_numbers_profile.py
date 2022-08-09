class HierCCNumbersProfile:
    """
    Class used to store Hc numbers from one sequence type and export it to mongoDB ready format.
    """
    def __init__(self, data: list, headers: list = None):
        """
        Initialize the class
        :param data: the list of hiercc cluster numbers + st returned after clustering with the HierCC tool.
        :param headers: the list of headers from the result file from hiercc (can be extracter from the hiercc results
        collection in mongoDB.
        """
        self.st = data[0]
        self.hcnumbers = data[1:len(data)]
        if headers:
            self.hcc = headers[1:len(headers)]

    def get_hiercc_results_collection_entries(self) -> list:
        """
        Creates a list of dict containing the future entries of Hcc numbers collection to upload in mongoDB.
        :return:
        """
        collection_entries = []
        for (hcnumber, hcc) in zip(self.hcnumbers, self.hcc):
            collection_entries.append({'ST': int(self.st), 'HC': hcc, 'HC_number': int(hcnumber)})
        return collection_entries
