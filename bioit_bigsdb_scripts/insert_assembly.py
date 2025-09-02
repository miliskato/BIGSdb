import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import List

from Bio import SeqIO

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblIsolates, TblSequenceBin
from bioit_mongodb_scripts.model.json_model import ResultType
from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_mongodb_scripts.util.mongo_config_provider import MongoConfigProvider
from bioit_mongodb_scripts.util.mongo_quickdraw import get_pseudo_id


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--fastafilepath', required=True, type=Path)
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    argument_parser.add_argument('--isolatename', required=True, type=str)
    argument_parser.add_argument('--results_type', required=True, type=ResultType)
    return argument_parser.parse_args()


def insert_assembly(isolatename: str, species: str, fastafilepath: Path, results_type: ResultType) -> None:
    """
    Inserts an assembly for a given sample in bigsdb
    :param isolatename: name of the isolate in bigsdb
    :param species: commonly used bioit species name: either genus or specific like stec
    :param fastafilepath: path of the fasta file
    :param results_type: string defining if we are handling a new isolate or a positively validated goodqc / warningqc
    / reseq.
    :return: None
    """
    try:
        # Connect to db and create cursors
        with TblIsolates(species) as isolates_psql_tbl, TblSequenceBin(species) as isolates_seqbin_psql_tbl:
            sample_presence = isolates_psql_tbl.count_isolate((isolatename,))
            if sample_presence[0][0] == 0:
                send_email(f"please insert isolate/isolate results first",
                           f'{Path(__file__).name}: Error inserting assembly of {species} pipeline to bigsdb for '
                           f'sample {isolatename} on host {socket.gethostname()}.')
                sys.exit()

            presentcontigs = isolates_seqbin_psql_tbl.count_sequencebin((isolatename,))
            if presentcontigs[0][0] != 0 and results_type == 'resequencing':
                isolates_seqbin_psql_tbl.delete_sequencebin((isolatename,))

            if MongoConfigProvider.is_viral(species):
                _process_viral_consensus(fastafilepath, isolatename, isolates_seqbin_psql_tbl, species)
            else:
                for record in SeqIO.parse(fastafilepath, "fasta"):
                    isolates_seqbin_psql_tbl.insert_sequencebin((isolatename, str(record.seq), record.id))

    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                   f'{Path(__file__).name}: Error inserting assembly of {species} pipeline to bigsdb for '
                   f'sample {isolatename} on host {socket.gethostname()}.')
        sys.exit()


def _process_viral_consensus(fastafilepath: Path, isolatename: str, isolates_seqbin_psql_tbl: TblSequenceBin, species:str) -> None:
    """
    Inserts (viral) contigs into bigsdb while replacing pseudo_id by isolatename in the contig names.
    :param fastafilepath: path of the fasta file for consensus sequence
    :param isolatename: name of the isolate in bigsdb
    :param isolates_seqbin_psql_tbl: psql table seqbin from the bigsdb_xxx_isolates DB
    :param species: species name
    :return: None
    """
    modified_records = []
    for record in SeqIO.parse(fastafilepath, "fasta"):
        pseudo_id = get_pseudo_id(species, isolatename)
        new_id = record.id.replace(pseudo_id, isolatename)
        if record.seq:
            isolates_seqbin_psql_tbl.insert_sequencebin((isolatename, str(record.seq), new_id))


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Get Bigsdb config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species']))

    # run main
    insert_assembly(args.isolatename, args.species, args.fastafilepath, args.results_type)
