import argparse
import logging
from pathlib import Path
import socket
import sys
from typing import List
from bioit_bigsdb_scripts.components.python_utility_functions import send_email
from bioit_bigsdb_scripts.components.psql import (TblIsolates, TblSubmissions, TblIsolateSubmissionIsolates)
from psql.databaseconnection import (get_bigsdb_config_data)


PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


def insert_lab_metadata_through_bigs(species: str):
    """
    Inserts lab metadata submitted through bigsdb built-in upload tool
    :param species: commonly used bioit species name: either genus or specific like stec
    :return: None
    """
    with TblSubmissions(species) as isolates_sub_psql_tbl, \
            TblIsolateSubmissionIsolates(species) as isolates_isosubiso_psql_tbl, \
            TblIsolates(species) as isolates_psql_tbl:

        isolates_returned = isolates_psql_tbl.listing_isolates()
        isolates_already_in_bigs = []
        for i in isolates_returned:
            isolates_already_in_bigs.append(list(i)[0])

        submission_ids = isolates_sub_psql_tbl.get_submission_id_from_bigs_upload()
        if len(submission_ids) > 0:
            for submitted_id in submission_ids:
                lab_metadata = isolates_isosubiso_psql_tbl.get_field_and_value_from_submission(submitted_id)

                metadata_dict = {}
                for i in range(1, len(lab_metadata) - 1):
                    if lab_metadata[i][2] == 'isolate':
                        isolate_id = lab_metadata[i][3]
                    else:
                        metadata_dict[lab_metadata[i][2]] = lab_metadata[i][3]

                if isolate_id in isolates_already_in_bigs:
                    # prepare query
                    isolate_update_query = TblIsolates.build_update_nomin_metadata_query(metadata_dict)
                    params = []
                    for key in metadata_dict:
                        params.append(metadata_dict[key])
                    params.append(isolate_id)
                    isolates_psql_tbl.update_nomin_metadata(isolate_update_query, params)
                else:
                    send_email(f"Insertion failed: Isolate {isolate_id} not found in bigsDB",
                               subject=f"Metadata insertion on host {socket.gethostname()}")

                isolates_sub_psql_tbl.update_submission(submitted_id)


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Get Bigsdb config
    bigsdb_config_data = get_bigsdb_config_data()

    args = parse_arguments(specieslist=['neisseria'])

    # run main
    insert_lab_metadata_through_bigs(args.species)
