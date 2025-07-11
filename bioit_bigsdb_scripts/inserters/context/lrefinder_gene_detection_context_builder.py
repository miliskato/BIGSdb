from typing import Any, Dict
import pandas as pd

from bioit_bigsdb_scripts.inserters.context.gene_detection_context import GeneDetectionContext
from bioit_bigsdb_scripts.inserters.context.gene_detection_context_builder import GeneDetectionContextBuilder


class LreFinderGeneDetectionContextBuilder(GeneDetectionContextBuilder):
    """
    Builder of context specific to the ResFinder4 gene detection scheme.
    """
    SCHEME_NAME = 'lrefinder'

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
        bigsdb_scheme_name = scheme_config['schemename_bigsdb']
        file_path = scheme_config['metadatafile']
        mutations = pd.read_csv(file_path, delimiter="_", header=None)
        mutations["sequence_id"] = mutations[[0, 1, 2]].agg('_'.join, axis=1)
        mutations["bigsdb_genecluster_name"] = bigsdb_scheme_name + "_" + mutations[0] + "_" + mutations[2]
        accession_ids = mutations[2].to_list()
        sequence_ids = mutations["sequence_id"].to_list()
        bigsdb_genecluster_names = mutations["bigsdb_genecluster_name"].to_list()

        for index, accession_id in enumerate(accession_ids):
            bigsdb_genecluster_name = bigsdb_genecluster_names[index]
            sequence_id = sequence_ids[index]
            context.set_sequence_genecluster_name(sequence_id, bigsdb_genecluster_name)
            context.add_description(bigsdb_genecluster_name, accession_id)
        return context
