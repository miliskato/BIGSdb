import argparse
import socket
import sys
from pathlib import Path
from typing import List, Tuple

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email
from bioit_bigsdb_scripts.components.psql.databaseconnection import DatabaseConnection
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', type=str, choices=specieslist)
    return argument_parser.parse_args()


class TblSubmissionslocal(DatabaseConnection):
    """
    submissions table in the isolates database
    """

    def __init__(self, species: str) -> None:
        """
        Initialises this class by opening a database connection.
        :param species: commonly used bioit species name: either genus or specific like stec
        :return: None
        """
        self._db_type = 'isolates'
        super().__init__(species, self._db_type)

    def get_submission_id_from_bigs_upload(self) -> List[Tuple[str]]:
        """
        Select submission ids submitted through bigsDB interface with status closed
        :return: List of corresponding submissions id
        """
        str_query = """SELECT value FROM isolate_submission_isolates where submission_id in (SELECT id FROM submissions 
            where validation_type = 'bad_quality' and status = 'pending') and field = 'isolate_id';"""
        return self.execute(str_query)


if __name__ == '__main__':

    # Parse config
    mongo_config_data = get_mongodb_config_data()
    bigsdb_config_data = get_bigsdb_config_data()
    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))

    # Open collections
    mongoinit = MongoInitialisation(args.species,
                                    selected_connection_string='CONNECTION_STRING_AZURE',
                                    mongo_config_data=mongo_config_data)
    _, _, isolates_badqc_collection, _ = mongoinit.initialise_collections()
    mongoinit_local = MongoInitialisation(args.species,
                                          selected_connection_string='CONNECTION_STRING_LOCAL',
                                          mongo_config_data=mongo_config_data)
    mappingtable_collection = mongoinit_local.initialise_mapping_table_collection()
    all_badqc = isolates_badqc_collection.find({}, {'id': 1})
    list_badqc = list(all_badqc)
    list_pseudo_id_badqc = [x.get('_id') for x in list_badqc]
    mapping_badqc = mappingtable_collection.find({"pseudo_id": {"$in": list_pseudo_id_badqc}}, {"_id": 1})
    mapping_badqc_list = list(mapping_badqc)
    atlas_badqc_isolate_name = [x.get('_id') for x in mapping_badqc_list]
    bigsdb_submited_isolates = []
    with TblSubmissionslocal('mycobacterium') as tblsubmission:
        bigsdb_submissions = tblsubmission.get_submission_id_from_bigs_upload()
    for isolate_id in bigsdb_submissions:
        bigsdb_submited_isolates.append(list(isolate_id)[0])
    badqc_missing_in_bigsdb = list(set(atlas_badqc_isolate_name) - set(bigsdb_submited_isolates))

    if len(badqc_missing_in_bigsdb) != 0:
        send_email(
            content=f"Missing isolates were found in MongoDB but not in BIGSdb submissions table: {badqc_missing_in_bigsdb}",
            subject=f"Missing badqc on host {socket.gethostname()}")
