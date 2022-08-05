class HierCCCgMLSTProfile:
    def __init__(self, data: list):
        self.st = data[0]
        self.cgmlst = data[1:len(data)]

    def get_cgmlst_profile(self):
        return ','.join([str(i) for i in self.cgmlst])
