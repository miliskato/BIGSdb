from abc import abstractmethod
from typing import Any, Dict

from bioit_bigsdb_scripts.inserters.context.gene_detection_context import GeneDetectionContext


class GeneDetectionContextBuilder:
    """
    Abstract class that sets the contract for GeneDetectionContext
    """

    @abstractmethod
    def accept(self, scheme: str) -> bool:
        """
        Evaluate if the scheme should be accepted.
        :param scheme: name of the scheme
        :return: True if the scheme should be accepted by the builder otherwise False
        """
        pass

    @abstractmethod
    def build(self, scheme: str, scheme_config: Dict[str, Any]) -> GeneDetectionContext:
        """
        Based on metadata file containing the profiles of the scheme, creates dictionaries used to insert loci in seqdef
        :param scheme: name of the scheme
        :param scheme_config: bigsdb config for this scheme
        :return: GeneDetectionContext object
        """
        pass
