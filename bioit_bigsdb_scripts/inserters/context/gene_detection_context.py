from typing import Any, Dict, List


class GeneDetectionContext:
    """Class to create the context for the scheme of interest"""

    def __init__(self, scheme: str, scheme_config: Dict[str, Any]) -> None:
        """
        :param scheme: name of the scheme
        :param scheme_config: config from bigsdb config file for this scheme
        :return: None
        """
        self.scheme = scheme
        self.description_dict: Dict[str, List[str]] = {}
        self.cluster_dict: Dict[str, str] = {}
        self.scheme_config = scheme_config

    def add_description(self, gene_cluster: str, description: str) -> None:
        """
        Fills in dict with gene_cluster_name as keys and description of the gene_cluster (alleles/mutations) as values
        :param gene_cluster: gene cluster name
        :param description: description of the gene cluster components
        :return: None
        """
        if not self.description_dict.get(gene_cluster):
            self.description_dict[gene_cluster] = []
        self.description_dict[gene_cluster].append(description)

    def set_sequence_genecluster_name(self, sequence_id: str, bigsdb_genecluster_name: str) -> None:
        """
        Fills in dict with sequence_id as key and combination of bigsdb scheme name and gene cluster name as values
        :param sequence_id: sequence id
        :param bigsdb_genecluster_name: gene cluster name
        :return: None
        """
        self.cluster_dict[sequence_id] = bigsdb_genecluster_name
