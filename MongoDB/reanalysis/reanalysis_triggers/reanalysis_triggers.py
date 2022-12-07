import argparse
import yaml
from pymongo.read_concern import ReadConcern
import logging
import smtplib
from email.message import EmailMessage
import os
from pathlib import Path
import sys
import datetime
import git
import subprocess
import re
import concurrent.futures
import socket
import traceback
import json

PYTHONPATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(PYTHONPATH))

from MongoDB.reanalysis.reanalysis_triggers import TRIGGER_CONFIG
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.reanalysis.command.command import Command

# https://stackoverflow.com/questions/5685007/making-git-log-ignore-changes-for-certain-paths
# git log --date=short -- . ':(exclude)db_metadata.txt'


def _parse_arguments(specieslist) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, choices=specieslist, help='Species to re-analyze')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use in total')
    parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='eg /home/BIGSdb/3.9PythonVenv/bin/python3.9')
    parser.add_argument('--slurm', action='store_true', help='Run reanalyses using slurm, dont include to not use slurm')
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


if __name__ == '__main__':

    # Read the trigger config
    with open(TRIGGER_CONFIG, encoding='utf-8') as handle:
        trigger_config = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(list(trigger_config['species'].keys()))

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        mongo_config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    try:
        mongoinit = Mongoinitialisation()
        isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit.initialise_collections(
            mongo_config_data, args.species)

        # Part 1: Query scheme last update dates and sort schemes by last update date
        date_scheme_dict = {}
        for scheme in trigger_config['species'][args.species]:
            logging.debug(f"scheme {scheme}")
            os.chdir(Path(trigger_config['species'][args.species][scheme]['dirdb']))
            # set git repo to safe repo
            subprocess.run(f"git config --global --add safe.directory {trigger_config['species'][args.species][scheme]['dirdb'].replace('/db', '/var/lib/.bioit_database')}", shell=True)
            # query_date
            gitlog = subprocess.run("git log -n 1 --date=short -- . ':(exclude)db_metadata.txt'", shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
            scheme_last_update = re.findall("[0-9]{4}-[0-9]{2}-[0-9]{2}", gitlog)[0]
            trigger_config['species'][args.species][scheme]["last_update"] = scheme_last_update
            if scheme_last_update in date_scheme_dict.keys():
                date_scheme_dict[scheme_last_update] = ' '.join([date_scheme_dict[scheme_last_update], trigger_config['species'][args.species][scheme]['cmd_argument']])
            else:
                date_scheme_dict[scheme_last_update] = trigger_config['species'][args.species][scheme]['cmd_argument']
        # e.g. date_scheme_dict: {'2022-10-02': 'mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation', '2022-08-14': 'ncbi-amr', '2022-07-03': 'resfinder', '2020-06-24': 'virulencefinder plasmidfinder', '2019-03-04': 'vfdb-core'}

        # Part 2: Recursively/hierarchically add all schemes with higher last update date to lower update date
        date_args_dict = {}
        for index, last_update in enumerate(sorted(date_scheme_dict.keys())):
            date_args_dict[last_update] = ' '.join([date_scheme_dict[last_update] for last_update in sorted(date_scheme_dict)[index:]])
        # e.g. date_args_dict: {'2019-03-04': 'vfdb-core virulencefinder plasmidfinder resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation', '2020-06-24': 'virulencefinder plasmidfinder resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation', '2022-07-03': 'resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation', '2022-08-14': 'ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation', '2022-10-02': 'mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation'}

        # Part 3: run reanalysis
        source = os.path.dirname(__file__)
        parent = os.path.join(source, '../')
        def run_reanalysis(date: str, date_args_dict: dict) -> None:
            """
            Runs reanalysis.py on samples with last analysis date older than assay db updates
            :param date: datetimestring 'YYYY-MM-DD', key in date_args_dict
            :param date_args_dict: key (date): args(str) dict e.g. {'2019-03-04': 'vfdb-core virulencefinder'}
            :return: None
            """
            logging.info(f"running reanalysis on samples older than {date} with arguments: {date_args_dict[date]}")
            base_command = ' '.join([
                f"{args.pyvenvpythonpath}",
                f"{os.path.join(parent, 'reanalysis.py')}" if args.slurm is False else f"{os.path.join(parent, 'reanalysis_slurm_submitter.py')}",
                f'--species {args.species}',
                f'--maximal_analysis_date {date}'
                f' --analysis_arguments {date_args_dict[date]}',
                f'--pyvenvpythonpath {args.pyvenvpythonpath}',
                f"--threads {args.threads}" if args.slurm is False else f"--threads_per_job 1",
            ])
            command = Command(base_command)
            command.run(Path(os.getcwd()))
            if command.returncode != 0:
                # if pipeline fails, send mail and continue to next sample, dont raise error
                _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                            f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])
                # raise RuntimeError(f"Error executing pipeline: {command.stderr}")
            else:
                logging.info(f"Reanalysis for samples older than {date} with arguments: {date_args_dict[date]} completed")

        # with concurrent.futures.ThreadPoolExecutor(max_workers=1 if args.slurm is False else 5) as executor:  # MK 24th nov 2022, i dont remember why slurm would get 5 workers because this i think would cause isolates that need to be reanalyzed in the lowest date to also be captured in the next dates
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            #testing purposes
            # date_args_dict = {
            #     '2019-03-04': 'vfdb-core virulencefinder plasmidfinder resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2020-06-24': 'virulencefinder plasmidfinder resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2022-07-03': 'resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2022-08-14': 'ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     # '2024-10-02': 'cgmlst mlst',
            #     '2025-10-04': 'mlst'}
            future_to_isolate = {executor.submit(
                run_reanalysis, **{"date": date, "date_args_dict": date_args_dict}):
                               date for date in date_args_dict.keys()}
            logging.info(f"finished submitting reanalysis for species {args.species}")

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])
