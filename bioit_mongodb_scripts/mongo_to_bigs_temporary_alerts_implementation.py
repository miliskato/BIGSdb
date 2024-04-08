#!/usr/bin/env python

import argparse
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List

from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql import TblIsolates, TblSchemes
from bioit_mongodb_scripts.util.alerts_to_bigs import AlertsToBigs
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    return argument_parser.parse_args()


class MongoToBigsTemporaryAlertsImplementation:
    """
    Initializing this class will trigger its main function.
    This script is supposed to run periodically through a cronjob; based on discussion, preferably daily.
    For all isolates in the MongoDB database; check which do not have an isolation date, for those that do not,
    check whether they have an isolation date in bigs, if they do; evaluate alerts for those isolates that have
    an isolation date in bigs and not in mongo, and add the isolation date to mongo.
    """
    def __init__(self, species: str, mongo_config_data: Dict[str, Any] = None) -> None:
        """
        Initializes this class and executes the main function
        :param species: commonly used bioit species name: either genus or specific like stec
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :return: None
        """
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        self._species = species

        # Parse MongoDB config
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()

        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data)
        self._isolates_collection, self._old_isolateresults_collection, self._isolates_badqc_collection, \
            self._isolates_resequencing_collection = self._mongoinit.initialise_collections()
        self._headers_collection = self._mongoinit.initialise_headers_collection()

        with TblSchemes(self._species, 'isolates') as isolates_schemes_psql_tbl:
            self._cgmlst_bigsdb_scheme_id = isolates_schemes_psql_tbl.select_scheme_id_cgmlst()[0][0]

        # Execute main function
        try:
            self._mongo_to_bigs_temporary_alerts_implementation()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
            raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}: {exceptionmessage}\n{traceback.format_exc()}")


    def _mongo_to_bigs_temporary_alerts_implementation(self) -> None:
        """
        Main function.
        See Class description.
        """
        list_of_dicts_for_alerts = []

        # query all isolates without isolation date in mongodb
        isolates_wo_isolationdate = \
            list(self._isolates_collection.with_options(read_concern=ReadConcern(level="majority")).
                 find({'technical_metadata.isolation_date': {'$exists': False}}, {'_id': 1, 'results.cgST': 1}))
        isolates_wo_isolationdate_dict = {x['_id']: x for x in isolates_wo_isolationdate}
        tuple_isolates_wo_isolationdate = tuple(isolates_wo_isolationdate_dict.keys())

        with TblIsolates(self._species) as isolates_psql_tbl:
            isolates_w_isolationdates = isolates_psql_tbl.select_isolates_with_isolation_date((tuple_isolates_wo_isolationdate,))
        for isolate_tuple in isolates_w_isolationdates:
            dict_for_alerts = {'isolate_name': isolate_tuple[0], 'cgST': isolates_wo_isolationdate_dict[isolate_tuple[0]]['results'].get('cgST'),
                     'isolation_date': isolate_tuple[1].strftime('%d/%m/%Y - %X')}
            list_of_dicts_for_alerts.append(dict_for_alerts)
            self._isolates_collection.with_options(write_concern=WriteConcern(w="majority")).\
                update_one({'_id': isolate_tuple[0]}, {'$set': {'technical_metadata.isolation_date': isolate_tuple[1].strftime('%Y-%m-%d')}})
        if len(list_of_dicts_for_alerts) > 0:  # not needed to check this but more elegant
            AlertsToBigs(list_of_dicts_for_alerts, [], self._species, self._cgmlst_bigsdb_scheme_id)
        else:
            logging.info('no alerts to be computed')



if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse Mongo config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    MongoToBigsTemporaryAlertsImplementation(args.species, mongo_config_data=mongo_config_data)
