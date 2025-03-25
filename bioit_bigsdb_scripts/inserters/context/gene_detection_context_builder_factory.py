from typing import Any, Dict, List

from bioit_bigsdb_scripts.inserters.context.gene_detection_context import GeneDetectionContext
from bioit_bigsdb_scripts.inserters.context.amrfinder_gene_detection_context_builder import AmrFinderGeneDetectionContextBuilder
from bioit_bigsdb_scripts.inserters.context.gene_detection_context_builder import GeneDetectionContextBuilder
from bioit_bigsdb_scripts.inserters.context.generic_gene_detection_context_builder import GenericGeneDetectionContextBuilder
from bioit_bigsdb_scripts.inserters.context.resfinder4_gene_detection_context_builder import Resfinder4GeneDetectionContextBuilder

class GeneDetectionContextBuilderFactory:
    """
    Factory to create the context used to insert the scheme in seqdef.
    It can handle the context builders specified in the constructor.
    """

    def __init__(self):
        """Initiates the list of specific builders. The more generic builder must be kept as the last one in the list"""
        self.gene_detection_context_builders : List[GeneDetectionContextBuilder] = [
            Resfinder4GeneDetectionContextBuilder(),
            AmrFinderGeneDetectionContextBuilder(),
            GenericGeneDetectionContextBuilder()
        ]

    def build(self, scheme: str, scheme_config: Dict[str, Any]) -> GeneDetectionContext:
        """
        This method calls the right context builder among those specified in the constructor.
        :param scheme: The scheme for which a context is needed
        :param scheme_config: The configuration of the scheme
        :return: A GeneDetectionContext
        """
        for context_builder in self.gene_detection_context_builders:
            if context_builder.accept(scheme):
                return context_builder.build(scheme, scheme_config)
        raise Exception("Context builder not found for scheme {}".format(scheme))
