import json
from pathlib import Path
from typing import Any, Dict

from bioit_bigsdb_scripts.inserters.context.gene_detection_context import GeneDetectionContext
from bioit_bigsdb_scripts.inserters.context.gene_detection_context_builder import GeneDetectionContextBuilder

class GenericGeneDetectionContextBuilder(GeneDetectionContextBuilder):
    """
    Builder for gene detection context that catches all schemes except resfinder4 and amrfinder.
    """
    def accept(self, scheme: str) -> bool:
        """
        It always accepts the scheme as it is the last builder listed in the constructor of the factory
        :param scheme: name of the scheme
        :return: True
        """
        return True

    def build(self, scheme: str, scheme_config: Dict[str, Any]) -> GeneDetectionContext:
        """
        Based on "profiles.tsv" file from the corresponding db, creates dictionaries used to insert loci in seqdef
        :param scheme: name of the scheme
        :param scheme_config: bigsdb config for this scheme
        :return: GeneDetectionContext object
        """
        context = GeneDetectionContext(scheme, scheme_config)
        with Path(scheme_config['metadatafile']).open('r') as handle:
            sequencedictlist: Dict[str, Dict[str, Any]] = json.load(handle)
            # sequence id must be based on accession and allele/mutation because some schemes have duplicate accession numbers
            for sequencename in sequencedictlist:
                sequence_details = sequencedictlist[sequencename]
                if sequence_details['accession'] is None:
                    sequence_details['accession'] = "-"

                bigsdb_scheme_name = scheme_config['schemename_bigsdb']
                bigsdb_genecluster_name = f"{bigsdb_scheme_name}_Gene{sequence_details['cluster']}"

                context.set_sequence_genecluster_name(GenericGeneDetectionContextBuilder._create_sequence_id(sequence_details),
                                                      bigsdb_genecluster_name)

                key = 'allele' if bigsdb_scheme_name != 'VFDB_core' else 'gene'
                value = (sequence_details[key]).replace("'", "")
                context.add_description(bigsdb_genecluster_name, value)

        return context

    @staticmethod
    def _create_sequence_id(sequence_details: Dict[str, any]) -> str:
        """
        Generate the sequence_id which is a jonction of accession and allele items
        :param sequence_details: dictionary containing the details of the sequences
        :return: sequence_id
        """
        return '_'.join([(sequence_details['accession']), (sequence_details['allele']).replace("'", "")])