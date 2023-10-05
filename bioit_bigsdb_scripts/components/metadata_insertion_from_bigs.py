import argparse
import logging
import socket
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.python_utility_functions import send_email
from bioit_bigsdb_scripts.components.psql import TblIsolates, TblSubmissions, TblIsolateSubmissionIsolates
from psql.databaseconnection import get_bigsdb_config_data


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


def get_lab_metadata_dictionary(lab_metadata_from_query: List[Tuple]) -> Tuple[Dict[str, str], str]:
    """
    Handle results of the psql request which get back submissions from BIGSdb uploading tool
    :param lab_metadata_from_query: list of tuples containing lab metadata from the "isolate_submission_isolates" table.
    :return: Dictionary containing lab_metadata and string returning the isolate id.
    """
    metadata_dictionary = {}
    isolate_str = ''
    for i, item in enumerate(lab_metadata_from_query):
        if lab_metadata_from_query[i][2] == 'isolate':
            isolate_str = lab_metadata_from_query[i][3]
        else:
            metadata_dictionary[lab_metadata_from_query[i][2]] = lab_metadata_from_query[i][3]
    if isolate_str == '':
        send_email(f"Insertion failed: Isolate_id was missing for this submission, BigsDB should have refused the submission!",
                   subject=f"Metadata insertion failure on host {socket.gethostname()}")

    return metadata_dictionary, isolate_str


def insert_lab_metadata_through_bigs(species: str) -> None:
    """
    Inserts lab metadata submitted through bigsdb built-in upload tool
    :param species: commonly used bioit species name: either genus or specific like stec
    :return: None
    """
    with TblSubmissions(species) as isolates_sub_psql_tbl, \
            TblIsolateSubmissionIsolates(species) as isolates_isosubiso_psql_tbl, \
            TblIsolates(species) as isolates_psql_tbl:

        isolates_returned = isolates_psql_tbl.listing_isolates()
        isolates_already_in_bigs = {isolate[0] for isolate in isolates_returned}
        submission_ids = isolates_sub_psql_tbl.get_submission_id_from_bigs_upload()
        for submitted_id in submission_ids:
            lab_metadata = isolates_isosubiso_psql_tbl.get_field_and_value_from_submission(submitted_id)

            metadata_dict, isolate_id = get_lab_metadata_dictionary(lab_metadata)

            if isolate_id in isolates_already_in_bigs:
                # prepare query
                isolate_update_query = TblIsolates.build_update_nomin_metadata_query(metadata_dict)
                value_to_set_in_fields = [v for v in metadata_dict.values()]
                value_to_set_in_fields.append(isolate_id)
                isolates_psql_tbl.update_nomin_metadata(isolate_update_query, value_to_set_in_fields)
            else:
                send_email(f"Insertion failed: Isolate {isolate_id} not found in bigsDB",
                           subject=f"Metadata insertion failure on host {socket.gethostname()}")

            isolates_sub_psql_tbl.update_submission(submitted_id)


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Get Bigsdb config
    bigsdb_config_data = get_bigsdb_config_data()
    args = parse_arguments(list(bigsdb_config_data['species']))

    # run main
    insert_lab_metadata_through_bigs(args.species)
