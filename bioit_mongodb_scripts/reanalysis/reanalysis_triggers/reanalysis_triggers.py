import argparse
import concurrent.futures
import logging
import os
import re
import smtplib
import socket
import subprocess
import sys
import traceback
from email.message import EmailMessage
from pathlib import Path

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.reanalysis.reanalysis_triggers import TRIGGER_CONFIG
from bioit_mongodb_scripts.config import MONGO_CONFIG
from bioit_mongodb_scripts.mongo_to_bigs import mongo_to_bigs
from bioit_mongodb_scripts.reanalysis.reanalysis_slurm_submitter import reanalysis_slurm_submitter
from bioit_mongodb_scripts.reanalysis.reanalysis_noslurm import reanalysis_noslurm

# https://stackoverflow.com/questions/5685007/making-git-log-ignore-changes-for-certain-paths
# git log --date=short -- . ':(exclude)db_metadata.txt'


def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, choices=specieslist, help='Species to re-analyze')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use in total, only applicable when not using slurm since slurm knows how many threads are available')
    parser.add_argument('--pyvenvpythonpath', type=Path, help='eg /home/bigsdb/BIGSdb/3.9PythonVenv/bin/python3.9, required when using slurm')
    parser.add_argument('--slurm', action='store_true', help='Run reanalyses using slurm, dont include to not use slurm')
    parser.add_argument('--alternate_connection_string', action='store_true', help=argparse.SUPPRESS)
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

def reanalysis_triggers(species: str, threads: int = 8, pyvenvpythonpath: str = None, alternate_connection_string: bool = False, slurm = False) -> None:
    """
    Main function
    See argparse function for variables and their requiredness
    :param species:
    :param threads:
    :param pyvenvpythonpath:
    :param alternate_connection_string:
    :param slurm:
    :return:
    """
    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        mongo_config_data = yaml.safe_load(handle)

    # Read the trigger config
    with open(TRIGGER_CONFIG, encoding='utf-8') as handle:
        trigger_config = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    try:
        # Part 1: Query scheme last update dates and sort schemes by last update date
        date_scheme_dict = {}
        for scheme in trigger_config['species'][species]:
            logging.debug(f"scheme {scheme}")
            os.chdir(Path(trigger_config['species'][species][scheme]['dirdb']))
            # set git repo to safe repo
            subprocess.run(f"git config --global --add safe.directory {trigger_config['species'][species][scheme]['dirdb'].replace('/db', '/var/lib/.bioit_database')}", shell=True)
            # query_date
            gitlog = subprocess.run("git log -n 1 --date=short -- . ':(exclude)db_metadata.txt'", shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
            scheme_last_update = re.findall("[0-9]{4}-[0-9]{2}-[0-9]{2}", gitlog)[0]
            trigger_config['species'][species][scheme]["last_update"] = scheme_last_update
            if scheme_last_update in date_scheme_dict:
                date_scheme_dict[scheme_last_update].append(trigger_config['species'][species][scheme]['cmd_argument'])
            else:
                date_scheme_dict[scheme_last_update] = [trigger_config['species'][species][scheme]['cmd_argument']]
        # e.g. date_scheme_dict: {'2022-10-02': ['mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation',
        #                         '2022-08-14': ['ncbi-amr'],
        #                         '2022-07-03': ['resfinder'],
        #                         '2020-06-24': ['virulencefinder', 'plasmidfinder'],
        #                         '2019-03-04': ['vfdb-core']}

        # Part 2: Recursively/hierarchically add all schemes with higher last update date to lower update date
        from collections import OrderedDict
        date_args_dict = {}
        for index, last_update in enumerate(sorted(date_scheme_dict)):
            date_args_dict[last_update] = date_scheme_dict[last_update]
            for last_update_later in sorted(date_scheme_dict)[index:]:
                date_args_dict[last_update].extend(date_scheme_dict[last_update_later])
        # e.g. date_args_dict: {'2019-03-04': ['vfdb-core', 'virulencefinder', 'plasmidfinder', 'resfinder', 'ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2020-06-24': ['virulencefinder', 'plasmidfinder', 'resfinder', 'ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2022-07-03': ['resfinder', 'ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2022-08-14': ['ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2022-10-02': ['mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation']}

        # Part 3: run reanalysis
        def run_reanalysis(date: str, date_args_dict: dict) -> None:
            """
            Runs reanalysis.py on samples with last analysis date older than assay db updates
            :param date: datetimestring 'YYYY-MM-DD', key in date_args_dict
            :param date_args_dict: key (date): args(str) dict e.g. {'2019-03-04': 'vfdb-core virulencefinder'}
            :param ordered_dates_list: ordered list of dates, used to determine minimal analysis date
            :return: None
            """
            try:
                ordered_dates_list = sorted(date_args_dict)
                index_date_in_list = ordered_dates_list.index(date)
                minimal_date = ordered_dates_list[index_date_in_list - 1] if index_date_in_list != 0 else '1990-01-01'
                logging.info(f"running reanalysis on samples older than {date} and younger than {minimal_date} with arguments: {date_args_dict[date]}")
                arguments = {'species': species,
                             'maximal_analysis_date': date,
                             'minimal_analysis_date': minimal_date,
                             'analysis_arguments': date_args_dict[date],
                             'alternate_connection_string': alternate_connection_string}
                if slurm is False:
                    arguments['threads'] = threads
                    reanalysis_noslurm(**arguments)
                else:
                    arguments['pyvenvpythonpath'] = pyvenvpythonpath
                    arguments['threads_per_job'] = 1
                    reanalysis_slurm_submitter(**arguments)

                logging.info(f"Reanalysis for samples older than {date} with arguments: {date_args_dict[date]} completed")
            except Exception as exceptionmessage:
                _send_email(f"{Path(__file__).name} fail on host {socket.gethostname()}",
                            f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])
                raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

        # with concurrent.futures.ThreadPoolExecutor(max_workers=1 if slurm is False else 5) as executor:  # MK 24th nov 2022, i dont remember why slurm would get 5 workers because this i think would cause isolates that need to be reanalyzed in the lowest date to also be captured in the next dates
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future_to_isolate = {executor.submit(
                run_reanalysis, **{"date": date, "date_args_dict": date_args_dict}):
                               date for date in date_args_dict}
            logging.info(f"finished submitting reanalysis for species {species}")

        if alternate_connection_string is False:
            # After all the reanalyses, execute mongo_to_bigs.py
            mongo_to_bigs(species)
            logging.info(f"Mongo to bigs after reanalysis completed")

    except Exception as exceptionmessage:
        _send_email(f"{Path(__file__).name} fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])
        raise Exception(f"{Path(__file__).name} fail on host {socket.gethostname()}")

if __name__ == '__main__':

    # Read the trigger config
    with open(TRIGGER_CONFIG, encoding='utf-8') as handle:
        trigger_config = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(list(trigger_config['species']))

    # run main
    reanalysis_triggers(args.species,
                        threads=args.threads,
                        pyvenvpythonpath=(args.pyvenvpythonpath if args.pyvenvpythonpath else None),
                        alternate_connection_string=(True if args.alternate_connection_string else False),
                        slurm=args.slurm
                        )
