import csv
from pathlib import Path
from typing import Any, Dict, Tuple

from bioit_bigsdb_scripts.inserters.context.gene_detection_context import GeneDetectionContext
from bioit_bigsdb_scripts.inserters.context.gene_detection_context_builder import GeneDetectionContextBuilder


class Resfinder4GeneDetectionContextBuilder(GeneDetectionContextBuilder):
    """
    Builder of context specific to the ResFinder4 gene detection scheme.
    """
    SCHEME_NAME = 'resfinder4'

    def accept(self, scheme: str) -> bool:
        """
        Accept or reject the scheme
        :param scheme: name of the scheme
        :return: True if accepted, False otherwise
        """
        return scheme == self.SCHEME_NAME

    def build(self, scheme: str, scheme_config: Dict[str, Any]) -> GeneDetectionContext:

        """
        Based on "/db/amrfinder/latest/AMRProt" file from AMRFinder db, creates dictionaries used to insert loci in seqdef
        :param scheme: name of the scheme
        :param scheme_config: bigsdb config for this scheme
        :return: GeneDetectionContext object
        """
        context = GeneDetectionContext(scheme, scheme_config)
        with Path(scheme_config['metadatafile']).open('r') as phenotypes:
            file_reader = csv.DictReader(phenotypes, delimiter="\t")
            for row in file_reader:
                gene_accession = row.get('Gene_accession no.')

                gene = self.custom_split(gene_accession, '_', 1)[0]
                accession = self.custom_split(gene_accession, '_', 2)[1]

                bigsdb_scheme_name = scheme_config['schemename_bigsdb']
                bigsdb_genecluster_name = f"{bigsdb_scheme_name}_{gene}"

                sequence_id = "_".join([gene, accession])
                context.set_sequence_genecluster_name(sequence_id, bigsdb_genecluster_name)
                context.add_description(bigsdb_genecluster_name, accession)
        return context

    @staticmethod
    def custom_split(string_to_split: str, separator: str, position_of_separator: int) -> Tuple[str, str]:
        """
        used to split string only on the ith occurence of the separator
        :param string_to_split: string
        :param separator: separator
        :param position_of_separator: occurence of the separator used to split the string
        :return: list of two strings
        """
        string_to_split = string_to_split.split(separator)
        return separator.join(string_to_split[:position_of_separator]), separator.join(string_to_split[position_of_separator:])