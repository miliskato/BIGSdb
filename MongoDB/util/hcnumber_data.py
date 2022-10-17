
class HCNumbersData:
    """
    class used to structure the results of a query where all the Hc numbers from a sequence type are retrieved
    """
    def __init__(self ,st: str, query_hc ) -> None:
        self.st = st
        self.hc_numbers = self.__import_query_hc_results(query_hc)
    def __import_query_hc_results(self, query_hc) -> dict:
        results = dict()
        for result in query_hc:
            results[result['HC']] = result['HC_number']
        return results

    def get_hc_number(self ,hc_number: str) -> int:
        return self.hc_numbers[hc_number]
