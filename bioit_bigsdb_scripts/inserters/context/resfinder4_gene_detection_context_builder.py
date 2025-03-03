import csv
from pathlib import Path
from typing import Any, Dict

from bioit_bigsdb_scripts.inserters.context.gene_detection_context import GeneDetectionContext
from bioit_bigsdb_scripts.inserters.context.gene_detection_context_builder import GeneDetectionContextBuilder

class Resfinder4GeneDetectionContextBuilder(GeneDetectionContextBuilder):
    """
    Builder of context specific to the ResFinder4 gene detection scheme.
    """
    SCHEME_NAME = 'resfinder4'

    def accept(self, scheme: str) -> bool:
        return scheme == self.SCHEME_NAME

    def build(self, scheme: str, scheme_config: Dict[str, Any]) -> GeneDetectionContext:

        """
        Based on "phenotypes.txt" file from ResFinder4, create dictionaries used to insert loci in seqdef
        :param scheme: name of the scheme
        :param scheme_config: bigsdb config for this scheme
        :return: GeneDetectionContext object
        """
        context = GeneDetectionContext(scheme, scheme_config)
        with Path(scheme_config['metadatafile']).open('r') as phenotypes:
            file_reader = csv.DictReader(phenotypes, delimiter="\t")
            for row in file_reader:
                gene_accession = row.get('Gene_accession no.')

                if len(gene_accession.split("_")) == 3:
                    gene, _, accession = gene_accession.split("_")
                else:
                    gene = gene_accession.split("_")[0]
                    accession = "_".join((gene_accession.split("_")[2], gene_accession.split("_")[3]))
                #🍌🍌🍌🍌🍌 add try catch

                bigsdb_scheme_name = scheme_config['schemename_bigsdb']
                bigsdb_genecluster_name = f"{bigsdb_scheme_name}_{gene}"

                sequence_id = "_".join([gene, accession])
                context.set_sequence_genecluster_name(sequence_id, bigsdb_genecluster_name)
                context.add_description(bigsdb_genecluster_name, accession)
        return context