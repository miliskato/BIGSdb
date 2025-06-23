from typing import List, Self


class HtmlTableBuilder:
    """General class to build the html table for gene detection results"""

    def __init__(self, headers: List[str], width_px: int = None) -> None:
        """initialize the general class HtmlTableBuilder
        :param headers: list of headers fields
        :param width_px: width of the table in pixels
        :return: None
        """
        self._table = ''
        self._cols = len(headers)
        self._open_table(width_px)
        self._add_header(headers)

    def _open_table(self, width_px: int = None) -> None:
        """
        initialize the html table
        :param width_px: width of the table in pixels
        :return: None
        """
        style = '' if width_px is None else f' style="width: {width_px}px;"'
        self._table += '<style>table.nice { text-align: center; border-collapse: separate }table.nice td:first-child { max-width: 50ch; overflow-wrap: anywhere }table.nice tr:nth-child(n+3) {background: #E4EFF3}table.nice tr:nth-child(2n+3) {background: #C1E6F3}</style>'
        self._table += f'<table class="data nice"{style}>'

    def _add_header(self, headers: List[str]) -> None:
        """
        add headers to the html table
        :param headers: list of headers fields
        :return: None
        """
        self._table += f'<tr align="left">'
        for header in headers:
            self._table += f'<th>{header}</th>'
        self._table += f'</tr>'

    def add_report_row(self, report_url: str) -> None:
        """
        add hyperlink to the html report url
        :param report_url: url to call the api to get the html report
        :return: None
        """
        self._table += f'<td colspan="{self._cols}"><a href="{report_url}" target="_blank">Full report</a></td></tr>'

    def _close_table(self) -> None:
        """
        close the html table
        :return: None
        """
        self._table += '</table>'

    def add_row(self, values: List[str]) -> Self:
        """
        add row of results to the html table
        :param values: list of values to fill in the row
        :return: self
        """
        if len(values) != self._cols:
            raise IndexError('The number of values does not match the number of columns')

        self._table += f'<tr align="left">'
        for value in values:
            self._table += f'<td>{value}</td>'
        self._table += f'</tr>'
        return self

    def build(self) -> str:
        """
        will close the table and return the string encoding the html table
        :return: html string encoding the html table
        """
        self._close_table()
        return self._table


class HtmlReportBuilder:
    def __init__(self) -> None:
        """initialize the general class HtmlReportBuilder to link multiple html tables in a convenient layout
        :return: None
        """
        self._html = ''

    def add_title(self, title: str) -> None:
        self._html += f'<h3>{title}</h3>'

    def add_table(self, table_builder: HtmlTableBuilder) -> None:
        self._html += table_builder.build()
        self._html += f'<br />'

    def build(self) -> str:
        """
        :return: The html report
        """
        return self._html


class HtmlLocusTableBuilder(HtmlTableBuilder):
    """subclass used to create the html table following the format GeneCluster | Locus"""

    def __init__(self, report_url: str) -> None:
        """
        :param report_url: url to call the api to get the html report
        :return: None
        """
        super().__init__(headers=['GeneCluster', 'Locus'], width_px=500)
        self.add_report_row(report_url)

    def add_locus(self, gene_cluster: str, locus: str) -> None:
        """
        add locus to the html table
        :param gene_cluster: gene cluster
        :param locus: locus
        :return: None
        """
        self.add_row([gene_cluster, locus])


class HtmlAmrTableBuilder(HtmlTableBuilder):
    """subclass used to create the html table following the format for AMR resistances"""

    def __init__(self, report_url: str) -> None:
        """
        :param report_url: url to call the api to get the html report
        :return: None
        """
        super().__init__(headers=['AMR', 'Resistance gene', '%Identity', '%Coverage'], width_px=700)
        self.add_report_row(report_url)

    def add_hit(self, amr: str, resistance_gene: str, identity: str, coverage: str) -> None:
        """
        add hit to the html table
        :param amr: amr
        :param resistance_gene: resistance gene
        :param identity: identity
        :param coverage: coverage
        :return: None
        """
        self.add_row([amr, resistance_gene, identity, coverage])


class LreFinderGenesTableBuilder(HtmlTableBuilder):
    """subclass used to create the html table following the format for LRE-Finder"""

    def __init__(self, report_url: str) -> None:
        """
        :param report_url: url to call the api to get the html report
        :return: None
        """
        super().__init__(headers=['AMR', 'Gene', 'Template Identity', 'Depth'], width_px=700)
        self.add_report_row(report_url)

    def add_hit(self, resistance_gene: str, identity: str, depth: str) -> None:
        """
        add hit to the html table
        :param resistance_gene: resistance gene
        :param identity: template identity
        :param depth: depth
        :return: None
        """
        self.add_row(['Linezolid', resistance_gene, identity, depth])


class LreFinderMutationsTableBuilder(HtmlTableBuilder):
    """subclass used to create the html table following the format for LRE-Finder"""

    def __init__(self, report_url: str) -> None:
        """
        :param report_url: url to call the api to get the html report
        :return: None
        """
        super().__init__(headers=['Position in reference', 'Wild type ratio (%)', 'Mutant type ratio (%)', 'Predicted phenotype'], width_px=700)
        self.add_report_row(report_url)

    def add_hit(self, mutation_position: str, wt_ratio: str, mt_ratio: str, phenotype: str) -> None:
        """
        add hit to the html table
        :param mutation_position: position of the mutation in reference gene
        :param wt_ratio: ratio of wild type
        :param mt_ratio: ratio of mutant type
        :param phenotype: phenotype (resistant/sensitive) predicted based on the genomic results
        :return: None
        """
        self.add_row([mutation_position, wt_ratio, mt_ratio, phenotype])


class HtmlMobSuiteTableBuilder(HtmlTableBuilder):
    """subclass used to create the html table following the for Mob-suite results"""

    def __init__(self, report_url: str) -> None:
        """
        :param report_url: url to call the api to get the html report
        :return: None
        """
        super().__init__(headers=['id', 'num. contigs', 'size', 'GC content', 'predicted mobility', 'rep type(s)', 'relaxase types'], width_px=800)
        self.add_report_row(report_url)

    def add_plasmid(self, id: str, num_contigs: str, size: str, gc_content: str, predicted_mobility: str, rep_types: str, relaxase_types: str) -> None:
        """
        add characteristics of the plasmid detected by Mob-suite
        :param id: plasmid id
        :param num_contigs: number of contigs
        :param size: plasmid size
        :param gc_content: plasmid gc content
        :param predicted_mobility: predicted mobility
        :param rep_types: rep types
        :param relaxase_types: relaxase types
        :return: None
        """
        self.add_row([id, num_contigs, size, gc_content, predicted_mobility, rep_types, relaxase_types])


class HtmlLreFinderGenesTableBuilder(HtmlTableBuilder):
    """subclass used to create the html table following the LRE-Finder results for genes detected"""

    def __init__(self, report_url: str) -> None:
        """
        :param report_url: url to call the api to get the html report
        :return: None
        """
        super().__init__(headers=['Genes', '%Template identity', 'Depth'], width_px=500)
        self.add_report_row(report_url)

    def add_gene(self, gene_id: str, identity: str, depth: str) -> None:
        """
        add characteristics of the gene detected by LRE-Finder
        :param gene_id: gene identifier
        :param identity: % of identity with template
        :param depth: sequencing depth
        :return: None
        """
        self.add_row([gene_id, identity, depth])


class HtmlLreFinderMutationsTableBuilder(HtmlTableBuilder):
    """subclass used to create the html table following the LRE-Finder results for mutations detected"""

    def __init__(self, report_url: str) -> None:
        """
        :param report_url: url to call the api to get the html report
        :return: None
        """
        super().__init__(headers=['Position in reference', '%Wild type ratio', '%Mutant ratio', 'Predicted phenotype'], width_px=850)
        self.add_report_row(report_url)

    def add_mutation(self, mutation_position: str, wild_type_ratio: str, mutant_ratio: str, predicted_phenotype: str) -> None:
        """
        add characteristics of the gene detected by LRE-Finder
        :param mutation_position: mutation position
        :param wild_type_ratio: % of wild type
        :param mutant_ratio: % of mutant
        :param predicted_phenotype: predicted phenotype
        :return: None
        """
        self.add_row([mutation_position, wild_type_ratio, mutant_ratio, predicted_phenotype])
