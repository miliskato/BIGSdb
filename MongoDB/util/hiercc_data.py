from pathlib import Path
import gzip
class HierCCData:
    def __init__(self, input_data_path: Path):
        self.document_path = input_data_path
        self.data = []
        with gzip.open(self.document_path, "rb") as f:
            for line in f.readlines():
                if '#' in line:
                    self.header = self.__line_splitter(line)
                self.data.append(self.__line_splitter(line))
    def __line_splitter(self, raw_line: str):
        return raw_line.replace('\n','').split('\t')