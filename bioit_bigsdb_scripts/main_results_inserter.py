import argparse
import datetime
import json
import logging
import socket
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from bioit_mongodb_scripts.util.python_utility_functions import send_email

def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
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
    argument_parser.add_argument('--species', required=True, type=str, choices=specieslist)
    argument_parser.add_argument("--results_type", required=True, type=str, choices=['new_isolate', 'reanalysis'])
    argument_parser.add_argument("--report_access", required=True, type=str)
    return argument_parser.parse_args()


class MainResultsInserter:
    def __init__(self, isolatename: str, uploadermailadress: str, species: str, results_type: str, report_access: str,
                 jsonfilepath: Optional[Path] = None, tsvfilepath: Optional[Path] = None) -> None:
        """
        Initialises the class and runs the main function.
        See also argparse function for variables and their requiredness.
        :param isolatename: name of the isolate
        :param uploadermailadress: mailadress of the uploader
        :param species: commonly used bioit species name: either genus or specific like stec
        :param results_type: results of sample
        :param report_access: report_directory from MongoDB
        :param jsonfilepath: Path of the input json file
        :param tsvfilepath: Path of the input tsv file
        :return: None
        """
        # Input parameters
        self._isolatename = isolatename
        self._uploadermailadress = uploadermailadress
        self._species = species
        self._results_type = results_type
        self._report_access = report_access
        self._jsonfilepath = jsonfilepath
        self._tsvfilepath = tsvfilepath

        # Parameter compatibility checks
        if self._jsonfilepath and self._tsvfilepath:
            send_email(f"Choose one of both input methods",
                       f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            raise Exception(
                f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')

        # Execute main function
        try:
            self._main_results_inserter()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            raise Exception(f'{Path(__file__).name}: Error inserting isolate of {species} pipeline to bigsdb for sample {isolatename} on host {socket.gethostname()}.')
            
    def _main_results_inserter(self) -> None:
        """
        Main function, inserts isolate and its results into BIGSdb.
        :return: None
        """
        self._bigsdb_config_data = get_bigsdb_config_data()
    
        # parse input
        sample_output_dict = self.__parse_input()

        # fail safe mechanism is initated before inserting the isolate
        # fail safe mechanism uses a flagfile to lock the isolate insertion and checks whether the previous insertion of the isolate succeeded.
        with TblIsolates(self._species) as isolates_psql_tbl:
            self.__fail_safe_mechanism(sample_output_dict['analysis_date'], isolates_psql_tbl)
        maininserter = MainInserter(self._isolatename, self._species, sample_output_dict, self._bigsdb_config_data, self._report_access)
        if self._results_type == 'new_isolate':
            maininserter.insert_new_isolate(self._uploadermailadress)
        elif self._results_type == 'reanalysis':
            maininserter.insert_new_isolate_version()
        maininserter.insert_main_metadata()
        if self._tsvfilepath:
            with DatabaseConnection(self._species, 'isolates') as isolates_psql_db, \
                    DatabaseConnection(self._species, 'seqdef') as seqdef_psql_db:
                TsvTypingResultsInserter().insert_typing_results(self._isolatename, self._species, self._bigsdb_config_data['species'][self._species]['typing_schemes'], sample_output_dict, isolates_psql_db, seqdef_psql_db)
                TsvGeneDetectionResultsInserter().insert_genedetection_results(self._isolatename, self._species, self._bigsdb_config_data['species'][self._species]['genedetection_schemes'], sample_output_dict, isolates_psql_db, seqdef_psql_db)
        elif self._jsonfilepath:
            JsonTypingResultsInserter(self._isolatename, self._species, sample_output_dict, self._bigsdb_config_data).insert_typing_results()
            JsonGeneDetectionResultsInserter(self._isolatename, self._species, sample_output_dict, self._bigsdb_config_data).insert_genedetection_results()
        logging.info('Finished inserting results')
        self.__delete_flagfile()

    def __parse_input(self) -> Dict[str, Any]:
        """
        Parses the input into a dictionary
        :return: results dictionary
        """
        if self._tsvfilepath:
            sample_output_dict: Dict[str, Any] = {}
            with self._tsvfilepath.open('r') as handle:
                tsvfile = handle.readlines()
            for line in tsvfile:
                sample_output_dict[line.split('\t')[0]] = line.split('\t')[1].strip('\n')
        elif self._jsonfilepath:
            with self._jsonfilepath.open('r') as handle:
                records: Dict[str, Any] = json.load(handle)
            if 'results' in records:
                # records come from mongodb
                sample_output_dict = records['results']
            else:
                # records come from the pipeline directly
                sample_output_dict = records
            return sample_output_dict
        else:
            send_email("Need either jsonfilepath or tsvfilepath",
                       f'{Path(__file__).name}: Error inserting output of {self._species} pipeline to bigsdb for sample {self._isolatename} on host {socket.gethostname()}')
            raise Exception(f'Need either jsonfilepath or tsvfilepath.')

    def ___make_flagfilepath(self) -> Path:
        """
        Returns the flag file path
        :return: flag file path
        """
        return Path(self._bigsdb_config_data['failsafe']['flag_dir']) / '.'.join([self._isolatename, self._bigsdb_config_data['failsafe']['flag_append']])

    def __fail_safe_mechanism(self, analysis_date: str, isolates_psql_tbl: TblIsolates) -> None:
        """
        Creates a flagfile if insertion is started and no flagfile is present.
        else insertion is started and flag file is present: remove highest version of sample and
         reinsert if multiple versions, if only one version, sample is reinserted in the main workflow below
        :param analysis_date: analysis date needed to insert new isolate version
        :param isolates_psql_tbl: isolates db isolates table/ connection instance for a given species
        :return: flag file present
        """
        try:
            if not Path(self._bigsdb_config_data['failsafe']['flag_dir']).is_dir():
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).mkdir(parents=True, exist_ok=True)
                Path(self._bigsdb_config_data['failsafe']['flag_dir']).chmod(0o755)
            flagfilepath = self.___make_flagfilepath()
            if flagfilepath.is_file():
                logging.warning(
                    f"fail safe mechanism detects that the bigsdb insertion for sample {self._isolatename} was started but didnt finish. Removing {self._isolatename} from Bigsdb to be able to restart inserting.")
                nr_of_versions: int = isolates_psql_tbl.count_isolate((self._isolatename,))[0][0]
                if nr_of_versions > 1:
                    isolates_psql_tbl.revert_newversion((self._isolatename,))
                    isolates_psql_tbl.delete_isolate([self._isolatename])
                    isolates_psql_tbl.insert_isolate_newversion((self._isolatename, self._isolatename, self._isolatename,
                                                                 datetime.datetime.strptime(analysis_date,
                                                                                            '%d/%m/%Y - %X').strftime(
                                                                     '%Y-%m-%d')))
                    isolates_psql_tbl.update_newversion([self._isolatename])
                else:
                    isolates_psql_tbl.delete_isolate([self._isolatename])
            else:
                flagfilepath.touch()
                flagfilepath.chmod(0o755)
                logging.info(f"flagfilepath {flagfilepath}")
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: bigsdb upload fail safe mechanism fail on host {socket.gethostname()}")

    def __delete_flagfile(self) -> None:
        """
        :return: None, Removes flagfile
        """
        flagfilepath: Path = self.___make_flagfilepath()
        try:
            flagfilepath.unlink()
        except Exception as exceptionmessage:
            send_email(f"{exceptionmessage}\n{traceback.format_exc()}",
                       f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")
            raise Exception(
                f"{Path(__file__).name}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}")


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Read the global config
    bigsdb_config_data = get_bigsdb_config_data()

    # Parse arguments
    args = parse_arguments(list(bigsdb_config_data['species_json']))

    # run main
    MainResultsInserter(args.isolatename, args.uploadermailadress, args.species, args.results_type, args.report_access, jsonfilepath=(args.jsonfilepath if args.jsonfilepath else None), tsvfilepath=(args.tsvfilepath if args.tsvfilepath else None))
