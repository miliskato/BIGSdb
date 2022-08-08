from pathlib import Path
import gzip
class HierCCData:
    """
    Class to import data of sequence types and HierCC numbers from HierCC.
    IMPORTANT: the first line with the header MUST start with # (comment)
    """
    def __init__(self, input_data_path: Path):
        self.document_path = input_data_path
        self.data = []
        with gzip.open(self.document_path, "rt") as f:
            for line in f.readlines():
                if '#' in line:
                    self.header = self.__line_splitter(line)
                    self.header[0] = self.header[0].replace("#", "")
                else:
                    self.data.append(self.__line_splitter(line))
    def __line_splitter(self, raw_line: str):
        return raw_line.replace('\n','').split('\t')
