import argparse
import datetime
import json
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Union

import psycopg2.extensions

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.psql.databaseconnection import DatabaseConnection
from bioit_bigsdb_scripts.components.maininserter import MainInserter
from bioit_bigsdb_scripts.components.tsv_typingresultsinserter import TsvTypingResultsInserter
from bioit_bigsdb_scripts.components.tsv_genedetectionresultsinserter import TsvGeneDetectionResultsInserter
from bioit_bigsdb_scripts.components.json_typingresultsinserter import JsonTypingResultsInserter
from bioit_bigsdb_scripts.components.json_genedetectionresultsinserter import JsonGeneDetectionResultsInserter
from bioit_bigsdb_scripts.components.psql import TblIsolates
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data, send_email


def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    argument_parser = argparse.ArgumentParser()
    mutually_exclusive_group = argument_parser.add_mutually_exclusive_group(required=True)
    mutually_exclusive_group.add_argument('--tsvfilepath', type=Path)
    mutually_exclusive_group.add_argument('--jsonfilepath', type=Path)
    argument_parser.add_argument('--isolatename', required=True, type=str)
    argument_parser.add_argument('--uploadermailadress', required=True, type=str)
    argument_parser.add_argument('--species', required=True, type=str,
                                 choices=specieslist)
    argument_parser.add_argument("--results_type", required=True, type=str, choices=['new_isolate', 'reanalysis'])
    return argument_parser.parse_args()


def __make_flagfilepath(isolatename: str, config: Dict[str, Any]) -> Path:
    """
    Returns the flag file path
    :param isolatename: part of flagname
    :param config: config containing the failsafe settings
    :return: flag file path
    """
    return Path(config['failsafe']['flag_dir']) / '.'.join([isolatename, config['failsafe']['flag_append']])


def _fail_safe_mechanism(isolatename: str, config: Dict[str, Any], analysis_date: str, isolates_psql_tbl: TblIsolates) -> None:
    """
    Creates a flagfile if insertion is started and no flagfile is present.
    else insertion is started and flag file is present: remove highest version of sample and
     reinsert if multiple versions, if only one version, sample is reinserted in the main workflow below
    :param isolatename:
    :param config: config containing the failsafe settings
    :param analysis_date: analysis date needed to insert new isolate version
    :param isolates_psql_tbl: isolates isolates table/ connection instance for a given species
    :return: flag file present
    """
    try:
        if not Path(config['failsafe']['flag_dir']).is_dir():
            Path(config['failsafe']['flag_dir']).mkdir(parents=True, exist_ok=True)
            Path(config['failsafe']['flag_dir']).chmod(0o777)
        flagfilepath = __make_flagfilepath(isolatename, config)
        if flagfilepath.is_file():
            logging.warning(f"fail safe mechanism detects that the bigsdb insertion for sample {isolatename} was started but didnt finish. Removing {isolatename} from Bigsdb to be able to restart inserting.")
            nr_of_versions: int = isolates_psql_tbl.count_isolate((isolatename,))[0][0]
            if nr_of_versions > 1:
                isolates_psql_tbl.revert_newversion((isolatename,))
                isolates_psql_tbl.delete_isolate((isolatename, isolatename))
                isolates_psql_tbl.insert_isolate_newversion((isolatename, isolatename, isolatename,
                                                             datetime.datetime.strptime(analysis_date, '%d/%m/%Y - %X').strftime('%Y-%m-%d')))
                isolates_psql_tbl.update_newversion((isolatename, isolatename, isolatename))
            else:
                isolates_psql_tbl.delete_isolate((isolatename, isolatename))
        else:
            flagfilepath.touch()
            flagfilepath.chmod(0o777)
            logging.info(f"flagfilepath {flagfilepath}")
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                   f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")
        raise Exception(f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")


def _delete_flagfile(isolatename: str, config: Dict[str, Any]) -> None:
    """
    :param isolatename:
    :param config: config containing the failsafe settings
    :return: Removes flagfile
    """
    flagfilepath: Path = __make_flagfilepath(isolatename, config)
    try:
        flagfilepath.unlink()
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                   f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")
        raise Exception(f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")

def main_results_inserter(isolatename: str, uploadermailadress: str, species: str, results_type: str, jsonfilepath: Path = None, tsvfilepath: Path = None) -> None:
    """
    Main function, inserts isolate and its results into bigsdb
    See argparse function for variables and their requiredness
    :param isolatename: name of the isolate
    :param uploadermailadress: mailadress of the uploader
    :param species: commonly used bioit species name: either genus or specific like stec
    :param results_type: results of sample
    :param jsonfilepath: Path of the input json file
    :param tsvfilepath: Path of the input tsv file
    :return:None
    """
    bigsdb_config_data = get_bigsdb_config_data()

    # parse output
    if tsvfilepath:
        sample_output_dict: Dict[str, Any] = {}
        with tsvfilepath.open('r') as handle:
            tsvfile = handle.readlines()
        for line in tsvfile:
            sample_output_dict[line.split('\t')[0]] = line.split('\t')[1].strip('\n')
    elif jsonfilepath:
        with jsonfilepath.open('r') as handle:
            records: Dict[str, Any] = json.load(handle)
        if 'results' in records:
            # records come from mongodb
            sample_output_dict = records['results']
        else:
            # records come from the pipeline directly
            sample_output_dict = records
    else:
        send_email("", f'{Path(__file__).name}: Error inserting output of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}, '
                       f'need either jsonfilepath or tsvfilepath.')
        sys.exit()
    # Logic
    try:
        # fail safe mechanism is initated at the same time of the isolate insertion, but after connecting to the PSQL db's
        maininserter = MainInserter(isolatename, species, sample_output_dict, bigsdb_config_data)
        with TblIsolates(species) as isolates_psql_tbl:
            _fail_safe_mechanism(isolatename, bigsdb_config_data, sample_output_dict['analysis_date'], isolates_psql_tbl)
        if results_type == 'new_isolate':
            maininserter.insert_new_isolate(uploadermailadress)
        elif results_type == 'reanalysis':
            maininserter.insert_new_isolate_version()
        try:
            maininserter.insert_main_metadata()
            if tsvfilepath:
                with DatabaseConnection(species, 'isolates') as isolates_psql_db, \
                        DatabaseConnection(species, 'seqdef') as seqdef_psql_db:
                    TsvTypingResultsInserter().insert_typing_results(isolatename, species, bigsdb_config_data['species'][species]['typing_schemes'], sample_output_dict, isolates_psql_db, seqdef_psql_db)
                    TsvGeneDetectionResultsInserter().insert_genedetection_results(isolatename, species, bigsdb_config_data['species'][species]['genedetection_schemes'], sample_output_dict, isolates_psql_db, seqdef_psql_db)
            elif jsonfilepath:
                JsonTypingResultsInserter(isolatename, species, sample_output_dict, bigsdb_config_data).insert_typing_results()
                JsonGeneDetectionResultsInserter(isolatename, species, sample_output_dict, bigsdb_config_data).insert_genedetection_results()
            logging.info('Finished inserting results')
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f'{Path(__file__).name}: Error inserting output of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            raise Exception(f'{Path(__file__).name}: Error inserting output of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            # super important to raise exception because else the flagging file is removed and the entire fail safe doesnt work
        _delete_flagfile(isolatename, bigsdb_config_data)
    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                   f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
        raise Exception(f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = _parse_arguments(list(bigsdb_config_data['species']))

    # run main
    main_results_inserter(args.isolatename, args.uploadermailadress, args.species, args.results_type, jsonfilepath=(args.jsonfilepath if args.jsonfilepath else None), tsvfilepath=(args.tsvfilepath if args.tsvfilepath else None))
