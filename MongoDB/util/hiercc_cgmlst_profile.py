class HierCCCgMLSTProfile:
    def __init__(self, data: list, headers: list = None):
        self.st = data[0]
        self.cgmlst = data[1:len(data)]
        if headers:
            self.loci = headers[1:len(headers)]

    def get_cgmlst_profile(self):
        return ','.join([str(i) for i in self.cgmlst])

    def get_st_collection_entry(self):
        return {'ST': int(self.st), 'cgMLST': self.get_cgmlst_profile()}

    def get_st_line_for_hiercc_input(self):
        return '\t'.join([self.st, '\t'.join(self.cgmlst)])

