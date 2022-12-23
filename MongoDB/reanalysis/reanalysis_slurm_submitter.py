# export PYTHONPATH=/home/mikelchtermans/Bigsdb_mongodb/BIGSdb
# /home/mikelchtermans/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/MongoDB/reanalysis/reanalysis.py --species listeria --config /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/MongoDB/reanalysis/config.yml --threads 30 --pyvenvpythonpath /home/mikelchtermans/3.9PythonVenv/bin/python3.9
import argparse
import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urljoin
import concurrent.futures
import os
import sys
import socket
import shutil
import requests
import yaml
import psycopg2
import subprocess
import datetime
import traceback
import smtplib
from email.message import EmailMessage
import datetime

from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern

PYTHONPATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.util.command.command import Command
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.reanalysis import MONGO_REANALYSIS_CONFIG


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
    parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='eg /home/BIGSdb/3.9PythonVenv/bin/python3.9')
    parser.add_argument('--maximal_analysis_date', type=str, required=True, help='YYYY-MM-DD')
    parser.add_argument('--alternate_connection_string', type=str, help=argparse.SUPPRESS)
    return parser.parse_args()


def _send_email(subject: str, content: str, config: dict) -> None:
    """
    Sends an email.
    :param subject: Mail subject
    :param content: Content of the message
    :return: None
    """
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = config['from']
    message['To'] = config['to']
    message.set_content(content)
    with smtplib.SMTP(config['host']) as s:
        s.send_message(message)
    logging.info(content)

def reanalysis_slurm_submitter(species: str, maximal_analysis_date: str, pyvenvpythonpath: str, threads_per_job: int = 1, analysis_arguments: list = None, alternate_connection_string: str = None):
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

        # Parse config
        with open(MONGO_CONFIG, encoding='utf-8') as handle:
            mongo_config_data = yaml.safe_load(handle)

        # Check if slurm installed:
        base_command = "sinfo -V"
        command = Command(base_command)
        command.run(Path(os.getcwd()))
        if command.returncode != 0:
            raise RuntimeError(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}: Slurm not installed")

        # Retrieve isolates that need to be re-analyzed
        mongoinit = Mongoinitialisation()
        isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit.initialise_collections(
            mongo_config_data, species)
        # query all the documents as a projection
        documents_list = [doc for doc in
                          isolates_collection.find({'latest_analysis_date': {"$lt": maximal_analysis_date}},
                                                   {"_id": 1, "fasta_path": 1, "vcf_path": 1,
                                                    "latest_analysis_date": 1})]
        logging.info(f"{len(documents_list)} isolates to be reanalyzed")

        source = os.path.dirname(__file__)

        # approach threadpoolexecutor
        def run_reanalysis(isolate: dict) -> None:
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
                base_command += f" --alternate_connection_string {alternate_connection_string}"
            command = Command(base_command)
            command.run(Path(os.getcwd()))
            if command.returncode != 0:
                # if pipeline fails, send mail and continue to next sample, dont raise error
                _send_email(
                    f'{os.path.basename(__file__)}: Error submitting slurm job for {species}, {isolate["_id"]} on host {socket.gethostname()}',
                    f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])
                # raise RuntimeError(f"Error executing pipeline: {command.stderr}")
            else:
                logging.info(f"Slurm submission for isolate '{isolate['_id']}' completed")

        # Slurm can schedule up to 10000 jobs, best to max 5000: reanalysis triggers launches max 5, times 1000 below is 5000 max
        with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
            future_to_isolate = {executor.submit(
                run_reanalysis, isolate):
                               isolate for isolate in documents_list}

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])
        
if __name__ == '__main__':

    # Read the reanalysis config
    with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
        reanalysis_config = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(list(reanalysis_config['species'].keys()))

    # run main
    reanalysis_slurm_submitter(args.species,
                               args.maximal_analysis_date,
                               args.pyvenvpythonpath,
                               threads_per_job=args.threads_per_job,
                               analysis_arguments=(args.analysis_arguments if args.analysis_arguments else None),
                               alternate_connection_string=(
                                   args.alternate_connection_string if args.alternate_connection_string else None))
