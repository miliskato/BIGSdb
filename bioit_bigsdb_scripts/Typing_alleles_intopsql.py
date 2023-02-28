# todo maybe add reverse check aswell to see if sequences are not retired, but why would they retire?

import argparse
import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

from Bio import SeqIO

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblSequences, TblAlleleDesignations
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email

def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=False, type=str, choices=specieslist, default=specieslist,
                                 nargs='+')  # this does allow for the same species multiple times but doesn't really matter, they're uniquely filtered using set() anyway
    return argument_parser.parse_args()


def _insert_alleles() -> None:
    """
    Main function to insert all alleles for the given species
    :return: None
    """
    for species in set(args.species):
        with TblAlleleDesignations(species) as isolates_ad_psql_tbl, TblSequences(species) as seqdef_sequences_psql_tbl:
            schemedict: Dict[str, Dict[str, str]] = bigsdb_config_data['species'][species]['typing_schemes']
            for scheme in schemedict:
                if schemedict[scheme].get('dirdb'):
                    dirs: List[Path] = [x for x in Path(schemedict[scheme]['dirdb']).iterdir() if x.is_dir() and not x.name.startswith('.')]
                    for directory in dirs:
                        # hidden directories (startswith('.') need to be skipped as
                        # well as directories containing loci from other schemes in neisseria
                        if species == 'neisseria' and \
                                ((scheme == 'neisseria_fhbpnucl' and
                                  (directory.name == 'fHbp_allele' or directory.name == 'fHbp_DNAfrag_Pasteur')) or
                                 (scheme == 'neisseria_fhbppept' and
                                  (directory.name != 'fHbp_allele' or directory.name != 'fHbp_DNAfrag_Pasteur'))):
                            continue
                        # Part 1: Python component
                        # Make dict of fasta file
                        fastafilepath: Path = directory / ''.join([directory.name.lower(), '.fasta'])
                        fasta_dict = {}
                        for record in SeqIO.parse(fastafilepath, "fasta"):
                            # add the record to the dictionary with the ID as the key and the sequence as the value
                            sequence_id = record.id.split('_')[-1]
                            fasta_dict[sequence_id] = str(record.seq)

                        # Part 2: PSQL component
                        rows: List[Tuple[str]] = seqdef_sequences_psql_tbl.select_allele_from_locus((directory.name,))
                        set_alleleid = set(item[0] for item in rows)

                        # Part_3: Compare the two lists
                        if len(set_alleleid) > 0:  # not necessary but makes it slightly more elegant for new locus allele sequences
                            ids_to_be_inserted = set(sequence_id for sequence_id in fasta_dict if sequence_id not in set_alleleid)
                        else:
                            ids_to_be_inserted = set(fasta_dict)

                        # Part_4: insert missing allele sequences into psql db
                        for sequence_id in ids_to_be_inserted:
                            try:
                                """
                                Sometimes alleles retire for seemingly no reason, and are added immediately after as a new allele id,
                                The observed ids that went through this were not in any profile or any allele designation in the isolate db
                                """
                                seqdef_sequences_psql_tbl.insert_sequence((directory.name, sequence_id, fasta_dict[sequence_id]))
                            except Exception:
                                """
                                Profiles are located in the seqdef db and will automatically update when the sequence db is updated through a rule.
                                Allele designations in the isolate db on the other hand will not, moreover, allele designations in the allele db 
                                do not need to be referring to a real allele in the seqdef db.
                                """
                                old_id = (seqdef_sequences_psql_tbl.select_allele_from_sequence((directory.name, fasta_dict[sequence_id])))[0][0]
                                # If empty then it will be a simple empty list '[]' and taking the index twice will throw an error
                                seqdef_sequences_psql_tbl.update_alleleid((sequence_id, directory.name, old_id))
                                isolates_ad_psql_tbl.update_designations((sequence_id, directory.name, old_id))


if __name__ == '__main__':

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    try:
        _insert_alleles()
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")
