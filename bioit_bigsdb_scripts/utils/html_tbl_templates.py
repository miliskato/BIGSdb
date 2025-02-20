from typing import Dict, List, Self

class HtmlTableBuilder:
    def __init__(self, headers: List[str]):
        self._table = ''
        self._cols = len(headers)
        self._open_table()
        self._add_header(headers)

    def _open_table(self):
        self._table += '<style>table.nice { text-align: center; border-spacing:0 }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
        self._table += '<table class="data nice">'

    def _add_header(self, headers: List[str]):
        self._table += f'<tr align="left">'
        for header in headers:
            self._table += f'<th>{header}</th>'
        self._table += f'</tr>'

    def add_report_row(self, report_url: str):
        self._table += f'<td colspan="{self._cols}"><a href="{report_url}" target="_blank">Full report</a></td></tr>'

    def _close_table(self):
        self._table += '</table>'

    def add_row(self, values: List[str]) -> Self:
        if len(values) != self._cols:
            raise IndexError('The number of values does not match the number of columns')

        self._table += f'<tr align="left">'
        for value in values:
            self._table += f'<td>{value}</td>'
        self._table += f'</tr>'
        return self

    def build(self) -> str:
        self._close_table()
        return self._table

class HtmlLocusTableBuilder(HtmlTableBuilder):
    def __init__(self, report_url: str):
        super().__init__(headers=['GeneCluster', 'Locus'])
        self.add_report_row(report_url)

    def add_locus(self, gene_cluster: str, locus: str):
        self.add_row([gene_cluster, locus])

class HtmlResFinder4TableBuilder(HtmlTableBuilder):
    def __init__(self, report_url: str):
        super().__init__(headers=['AMR', 'Resistance gene', '%Identity', 'Coverage'])
        self.add_report_row(report_url)

    def add_hit(self, amr: str, resistance_gene: str, identity: str, coverage: str):
        self.add_row([amr, resistance_gene, identity, coverage])