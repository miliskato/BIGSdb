# export PYTHONPATH=/home/mikelchtermans/Bigsdb_mongodb/BIGSdb
# /home/mikelchtermans/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/bioit_mongodb_scripts/reanalysis/reanalysis.py --species listeria --config /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/bioit_mongodb_scripts/reanalysis/config.yml --threads 30 --pyvenvpythonpath /home/mikelchtermans/3.9PythonVenv/bin/python3.9
import argparse
import concurrent.futures
import datetime
import json
import logging
import os
import socket
import sys
import traceback
from pathlib import Path
from typing import Dict, List

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.reanalysis import MONGO_REANALYSIS_CONFIG
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import send_email


def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, choices=specieslist, help='Species to re-analyze')
    parser.add_argument('--threads_per_job', type=int, default=1, help='Number of threads to use for one job, should be lower than the machines maximum')
    parser.add_argument('--analysis_arguments', nargs='+', required=False,
                        help='analysis arguments stripped off --, e.g. "--analysis_arguments cgmlst mlst"')
    parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='eg /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9')
    parser.add_argument('--maximal_analysis_date', type=str, required=True, help='YYYY-MM-DD')
    parser.add_argument('--minimal_analysis_date', type=str, required=True, help='YYYY-MM-DD')
    parser.add_argument('--alternate_connection_string', action='store_true', help=argparse.SUPPRESS)
    return parser.parse_args()


def reanalysis_slurm_submitter(species: str, maximal_analysis_date: str, minimal_analysis_date: str, pyvenvpythonpath: str,
                               threads_per_job: int = 1, analysis_arguments: List[str] = None, alternate_connection_string: bool = False) -> None:
    """
    Main function
    See argparse function for variables and their requiredness
    :param species:
    :param maximal_analysis_date:
    :param pyvenvpythonpath:
    :param threads_per_job:
    :param analysis_arguments:
    :param alternate_connection_string:
    :return:
    """
    try:
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Check if slurm installed:
        base_command = "sinfo -V"
        command = Command(base_command)
        command.run(Path(os.getcwd()))
        if command.returncode != 0:
            raise RuntimeError(f"{Path(__file__).name} fail on host {socket.gethostname()}: Slurm not installed")

        # capture start_time
        start_time_reanalysis = datetime.datetime.utcnow()

        # Retrieve isolates that need to be re-analyzed
        mongoinit = MongoInitialisation(species, alternate_connection_string=alternate_connection_string)
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
        # query all the documents as a projection
        documents_list = [doc for doc in
                          isolates_collection.find({'latest_analysis_date': {"$lt": maximal_analysis_date, "$gte": minimal_analysis_date}},
                                                   {"_id": 1, "fasta_path": 1, "vcf_path": 1,
                                                    "latest_analysis_date": 1})]
        logging.info(f"{len(documents_list)} isolates to be reanalyzed")

        source = os.path.dirname(__file__)

        # approach threadpoolexecutor
        def run_reanalysis(isolate: Dict[str, str]) -> Dict[str, str]:
            """
            Creates command, runs command, and checks if command completes
            :param isolate: isolate dictionary from MongoDB
            :return: None
            """
            base_command = ' '.join([
                f"sbatch "
                f"{pyvenvpythonpath}",
                f"{os.path.join(source, 'reanalysis_slurm.py')}",
                f'--species {species}',
                f' --analysis_arguments {" ".join([x for x in analysis_arguments])}',
                f'--pyvenvpythonpath {pyvenvpythonpath}',
                f"--threads {threads_per_job}",
                f"--isolate '{json.dumps(isolate)}'"
            ])
            if alternate_connection_string:
                base_command += f" --alternate_connection_string"
            command = Command(base_command)
            command_output = command.run(Path(os.getcwd()))
            if command.returncode != 0:
                # if pipeline fails, send mail and continue to next sample, dont raise error # Since the mailbomb, do raise an error
                reanalysis_outcome_dictionary = {'Outcome': 'Fail', 'Isolate': isolate['_id'], 'Traceback': f"Error executing automatic reanalysis pipeline on {species}, {isolate['_id']}, stderr: {command.stderr}"}
                return reanalysis_outcome_dictionary
            else:
                logging.info(f"Slurm submission for isolate '{isolate['_id']}' completed")
                return json.loads(command_output.stdout.decode())  # This is the reanalysis_outcome_dictionary or at least it should be # todo test

        # Slurm can schedule up to 10000 jobs, best to max 5000: reanalysis_triggers.py launches max 5, times 1000 below is 5000 max
        if documents_list != []:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                futures = {executor.submit(
                    run_reanalysis, isolate):
                                   isolate for isolate in documents_list}
                succes_counter = 0
                fail_counter = 0
                fail_logs = ''
                for future in futures:
                    result_dict = future.result()
                    if result_dict['Outcome'] == 'Success':
                        succes_counter += 1
                    else:
                        fail_counter += 1
                        fail_logs += f"{result_dict['Isolate']}\t{result_dict['Traceback']}\n"
                # Capture end_time reanalysis
                end_time_reanalysis = datetime.datetime.utcnow()
                timedelta_reanalysis = end_time_reanalysis - start_time_reanalysis
                send_email(
                    f"Ran from {start_time_reanalysis} to {end_time_reanalysis} for a total of {timedelta_reanalysis.days} days, {timedelta_reanalysis.seconds // 3600} hours, "
                    f"{(timedelta_reanalysis.seconds - (timedelta_reanalysis.seconds // 3600 * 3600)) // 60} minutes\n"
                    f"Succes Count: {succes_counter}\nFail Count: {fail_counter}\nFail Logs: {fail_logs}",
                    f"{Path(__file__).name} report on host {socket.gethostname()} at {datetime.datetime.utcnow()}")
                logging.info(
                    f"Ran from {start_time_reanalysis} to {end_time_reanalysis} for a total of {timedelta_reanalysis.days} days, {timedelta_reanalysis.seconds // 3600} hours, "
                    f"{(timedelta_reanalysis.seconds - (timedelta_reanalysis.seconds // 3600 * 3600)) // 60} minutes\n"
                    f"Succes Count: {succes_counter}\nFail Count: {fail_counter}\nFail Logs: {fail_logs}")
        else:
            logging.info('No isolates to be reanalyzed found')

    except Exception as exceptionmessage:
        send_email(f"{exceptionmessage}\n{traceback.format_exc()}")
        raise Exception(f"{exceptionmessage}\n{traceback.format_exc()}")


if __name__ == '__main__':

    # Read the reanalysis config
    with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
        reanalysis_config = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(list(reanalysis_config['species']))

    # run main
    reanalysis_slurm_submitter(args.species,
                               args.maximal_analysis_date,
                               args.minimal_analysis_date,
                               args.pyvenvpythonpath,
                               threads_per_job=args.threads_per_job,
                               analysis_arguments=(args.analysis_arguments if args.analysis_arguments else None),
                               alternate_connection_string=(True if args.alternate_connection_string else False))
