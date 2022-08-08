class HierCCNumbersProfile:
    def __init__(self, data: list, headers: list = None):
        self.st = data[0]
        self.hcnumbers = data[1:len(data)]
        if headers:
            self.hcc = headers[1:len(headers)]

    def get_hiercc_results_collection_entries(self):
        collection_entries = []
        for (hcnumber, hcc) in zip(self.hcnumbers, self.hcc):
            collection_entries.append({'ST': self.st, 'HC': hcc, 'HC_number': hcnumber})
        return collection_entries
