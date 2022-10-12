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

from MongoDB.reanalysis.reanalysis_triggers import TRIGGER_CONFIG
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG

# https://stackoverflow.com/questions/5685007/making-git-log-ignore-changes-for-certain-paths
# git log --date=short -- . ':(exclude)db_metadata.txt'

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, help='Species to re-analyze')
    # parser.add_argument('--config', type=Path, required=True, help='Configuration file')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use')
    # parser.add_argument('--analysis_arguments', nargs='+', required=False, help='analysis arguments stripped off --, e.g. "--analysis_arguments cgmlst mlst"')
    parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='/home/BIGSdb/3.9PythonVenv/bin/python3.9')
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

def _return_datetimeobj_from_YMDhms(datetimestring: str):
    return datetime.datetime.strptime(datetimestring, '%d/%m/%Y - %X').date()

if __name__ == '__main__':

    # Parse arguments
    args = _parse_arguments()

    # Read the trigger config
    with open(TRIGGER_CONFIG, encoding='utf-8') as handle:
       trigger_config = yaml.safe_load(handle)

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        mongo_config_data = yaml.safe_load(handle)

    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    try:
        mongoinit = Mongoinitialisation()
        isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(
            mongo_config_data, args.species)

        # keeping this commented here because although code is not needed here, it is a useful query
        # earliest_analysis_date_document = isolates_collection.with_options(
        #     read_concern=ReadConcern(level="majority")).find_one(
        #     {},
        #     sort=[('latest_analysis_date', 1)])
        # earliest_analysis_date = _return_datetimeobj_from_YMDhms(earliest_analysis_date_document['latest_analysis_date'])
        # logging.debug(f"earliest analysis date: {earliest_analysis_date}")

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
        def run_reanalysis(date, date_args_dict):
            source = os.path.dirname(__file__)
            parent = os.path.join(source, '../')
            logging.info(f"running reanalysis on samples older than {date} with arguments: {date_args_dict[date]}")
            subprocess.run(
                f"{args.pyvenvpythonpath} {os.path.join(parent, 'reanalysis.py')} --species {args.species} --threads {args.threads} --maximal_analysis_date {date} --analysis_arguments {date_args_dict[date]} --pyvenvpythonpath {args.pyvenvpythonpath}", shell=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            #testing purposes
            # date_args_dict = {
            #     '2019-03-04': 'vfdb-core virulencefinder plasmidfinder resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2020-06-24': 'virulencefinder plasmidfinder resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2022-07-03': 'resfinder ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2022-08-14': 'ncbi-amr mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2022-10-02': 'mlst cgmlst pcr-serogroup metal-detergent typing-virulence typing-amr species-confirmation',
            #     '2025-10-04': 'mlst'}
            future_to_isolate = {executor.submit(
                run_reanalysis, **{"date": date, "date_args_dict": date_args_dict}):
                               date for date in date_args_dict.keys()}
            logging.info(f"submitted reanalysis for species {args.species}")

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()}",
                f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])

