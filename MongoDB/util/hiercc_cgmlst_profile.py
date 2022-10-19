import datetime

class HierCCCgMLSTProfile:
    """
    Class used to store cgMLST profiles  and sequence type and export them into convenient formats.
    """
    def __init__(self, data: list, headers: list = None):
        """
        Initialize the class
        :param data: the st + cgmlst in a list (query from querymongo by assay and id)
        :param headers: the headers from the data (query from querymongo by assay and id also)
        """
        self.st = data[0]
        self.cgmlst = data[1:len(data)]
        if headers:
            self.loci = headers[1:len(headers)]

    def get_cgmlst_profile(self) -> str:
        """
        Concatenates all the cgmlst alleles into one string to return the cgmlst profile.
        :return:
        """
        return ','.join([str(i) for i in self.cgmlst])

    def get_st_collection_entry(self) -> dict:
        """
        Creates a dict containing the sequence type and the cgmlst profile to enter into the sequence type collection
        :return:
        """
        return {'ST': int(self.st), 'cgMLST': self.get_cgmlst_profile(), 'insertion_date': datetime.datetime.utcnow()}

    def get_st_line_for_hiercc_input(self) -> str:
        """
        Concatenates the st + all the cgmlst into one string to write it into the input file for HierCC
        :return:
        """
        return '\t'.join([str(self.st), '\t'.join(map(str, self.cgmlst))])
