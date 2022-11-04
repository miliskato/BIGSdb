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

from command.command import Command
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG
from MongoDB.reanalysis import MONGO_REANALYSIS_CONFIG


def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, help='Species to re-analyze')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use')
    parser.add_argument('--analysis_arguments', nargs='+', required=False,
                        help='analysis arguments stripped off --, e.g. "--analysis_arguments cgmlst mlst"')
    parser.add_argument('--pyvenvpythonpath', type=Path, required=True, help='eg /home/BIGSdb/3.9PythonVenv/bin/python3.9')
    parser.add_argument('--isolate', type=json.loads, required=True)
    return parser.parse_args()


# --host-url
# http://bioit-bigs-dev.sciensano.be
# --species
# mycobacterium
# --dir-fastq
# /testdata/camel/pipelines/
# --config
# /home/bebogaerts/PycharmProjects/CamelTemp/camel/scripts/reanalysis/config.yml
# --threads
# 4

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


def __make_flagfilepath(isolatename: str, config: dict) -> Path:
    """
    Returns the flagfile path based on the isolate name
    :param isolatename: name of the isolate
    :param config: config containing the flagfile directory path
    :return: Path
    """
    return Path(config['failsafe']['flag_dir']) / '.'.join([isolatename, config['failsafe']['flag_append']])


def _fail_safe_mechanism(isolatename: str, config: dict, mailconfig: dict, tmp_dir: str) -> None:
    """
    Creates a flagfile containing the temporary dictionary if the file doesnt exist, if it does, remove the previous temporary directory, the file, and recreate the file
    :param isolatename: name of the isolate
    :param config: config containing the flagfile directory path
    :param mailconfig: config containging the mailing dictionary
    :param tmp_dir: temporary working dir
    :return: None
    """
    try:
        if not os.path.isdir(Path(config['failsafe']['flag_dir'])):
            os.makedirs(Path(config['failsafe']['flag_dir']), exist_ok=True)
        flagfilepath = __make_flagfilepath(isolatename, config)
        if os.path.isfile(flagfilepath):
            tmp_dir_fail = Path(open(flagfilepath).readlines()[0])
            logging.warning(
                f"fail safe mechanism detects that the reanalysis for sample {isolatename} was started but didnt finish. Removing tmp_dir {tmp_dir_fail}.")
            shutil.rmtree(tmp_dir_fail)
            # remove flagfilepath with wrong tmp dir in case reanalysis fails again
            os.remove(flagfilepath)
        with open(flagfilepath, 'w') as handle:
            handle.write(tmp_dir)
        logging.info(f"flagfilepath {flagfilepath}")
    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)}: reanalysis fail safe mechanism fail on host {socket.gethostname()}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", mailconfig['mail'])


def _delete_flagfile(isolatename: str, config: dict, mailconfig: dict) -> None:
    """
    Removes the flagfile
    :param isolatename: name of the isolate
    :param config: config containing the flagfile directory path
    :param mailconfig: config containging the mailing dictionary
    :return: None
    """
    flagfilepath = __make_flagfilepath(isolatename, config)
    try:
        os.remove(flagfilepath)
    except Exception as exceptionmessage:
        _send_email(
            f"{os.path.basename(__file__)}: Could not remove flag file {flagfilepath} on host {socket.gethostname()}",
            f"{exceptionmessage}\n{traceback.format_exc()}", mailconfig['mail'])


if __name__ == '__main__':

    # Parse arguments
    args = _parse_arguments()

    # Read the reanalysis config
    with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
        reanalysis_config = yaml.safe_load(handle)

    try:
        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Parse config
        with open(MONGO_CONFIG, encoding='utf-8') as handle:
            mongo_config_data = yaml.safe_load(handle)

        # ! For testing, you can specify isolates manually here
        # documents_list = [{'_id':'Myco-DRR041783-ds', .......}]

        # Re-analyze the isolates (can be parallelized with a Snakemake workflow)
        # e.g. response_data['isolates'] : "isolates":["http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/3","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/4","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/5"]
        isolate_id = args.isolate['_id']
        logging.info(f"Starting reanalysis for {isolate_id}")

        # check if fasta path exists
        if os.path.isfile(Path(args.isolate['fasta_path'])):
            logging.info(f"Fasta file is real")
            # todo check if fasta is actually fasta or not empty or?
        else:
            logging.error('Invalid fastafilepath')
            _send_email(
                f"{os.path.basename(__file__)}: reanalysis fail on host {socket.gethostname()} because {isolate_id}'s fasta path is invalid: {args.isolate['fasta_path']}",
                "", mongo_config_data['mail'])
            sys.exit()

        temp_new_sample_name = '_'.join([isolate_id, str(datetime.date.today())])
        logging.info(f"new sample name: {temp_new_sample_name}")

        # Get a temporary working directory
        with Path(tempfile.mkdtemp(None, 're_analysis_', reanalysis_config['temp_dir'])) as dir_temp:

            # initialise fail-safe mechanism
            _fail_safe_mechanism(isolate_id, reanalysis_config, mongo_config_data, str(dir_temp))

            # Get the species-specific configuration
            config_species = reanalysis_config['species'][args.species]

            # Determine the output file paths
            dir_out = dir_temp / temp_new_sample_name
            dir_out.mkdir(exist_ok=True, parents=True)
            tsv_out = dir_out / 'report.tsv'
            html_out = dir_out / 'report.html'

            # Determine the options
            if args.analysis_arguments:
                available_options_list = config_species['options']
                accepted_options_list = []
                if args.species == 'mycobacterium' and 'vcf_path' not in args.isolate.keys():
                    available_options_list = config_species['options_without_vcf']
                for option in args.analysis_arguments:
                    option_reformatted = ''.join(['--', option])
                    if option_reformatted in available_options_list:
                        accepted_options_list.append(option_reformatted)
                    else:
                        raise RuntimeError(
                            f'option {option_reformatted} is not a valid reanalysis option for species {args.species}')
            # if no specific analysis arguments are given, perform all analyses
            else:
                accepted_options_list = config_species['options']
                if args.species == 'mycobacterium' and 'vcf_path' not in args.isolate.keys():
                    accepted_options_list = config_species['options_without_vcf']

            # Create the command to re-analyze the datasets
            base_command = ' '.join([
                f"module load {config_species['lmod']};",
                f"{config_species['main_script']}",
                f'--fasta {args.isolate["fasta_path"]}',
                f'--output-dir {dir_out}',
                f"--output-html {html_out}",
                f'--output-tsv {tsv_out}',
                f'--working-dir {dir_temp}',
                *accepted_options_list,
                f'--threads {args.threads}',
                f'--sample-name {isolate_id}'
            ])
            command = Command(base_command)

            # mycobacterium exception
            if args.species == 'mycobacterium':
                # if this vcf doesnt exist then pipeline will fail during execution and send a mail just like with any other error
                # check if vcf path exists
                # todo be sure that this vcf path is the unfiltered one
                if os.path.isfile(Path(args.isolate['vcf_path'])):
                    logging.info(f"vcf file is real")
                    command = Command(' '.join([base_command, f'--vcf-unfiltered {args.isolate["vcf_path"]}']))
                else:
                    logging.info(
                        f"No vcf file is provided, certain analyses can not be executed but will give an error if requested")
            # run the command
            command.run(dir_temp)
            if command.returncode != 0:
                # if pipeline fails, send mail and continue to next sample, dont raise error
                _send_email(
                    f'{os.path.basename(__file__)}: Error executing automatic reanalysis pipeline on {args.species}, {isolate_id}',
                    command.stderr, mongo_config_data['mail'])
                # raise RuntimeError(f"Error executing pipeline: {command.stderr}")
            else:
                logging.info(f"Re-analysis for isolate '{isolate_id}' completed")

                # # debugging purposes
                # if 1+1==3:
                #     continue
                # else:
                #     sample_name = 'S16BD02199'
                #     new_sample_name = 'S16BD02199_2022-09-14'
                #     uploader = 'mikeltestauto'
                #     dir_out = Path("/scratch/temp/re_analysis_pjx15wnq/S16BD02199_2022-09-14")

                _delete_flagfile(isolate_id, reanalysis_config, mongo_config_data)

                # Create command insertion MongoDB
                source = os.path.dirname(__file__)
                parent = os.path.join(source, '../')
                base_command = ' '.join([
                    f"{args.pyvenvpythonpath}",
                    f"{os.path.join(parent, 'mainmongo.py')}",
                    f'--results_type reanalysis',
                    f'--technical_id {isolate_id}',
                    f"--jsonfilepath {dir_out / 'report.json'}",
                    f"--species {args.species}"
                ])
                command = Command(base_command)
                # run the command
                command.run(dir_out)
                if command.returncode != 0:
                    # if pipeline fails, send mail and continue to next sample, dont raise error
                    _send_email(
                        f'{os.path.basename(__file__)}: Error inserting json into mongodb for automatic reanalysis pipeline on {args.species}, {isolate_id}',
                        command.stderr, mongo_config_data['mail'])
                else:
                    logging.info(f"Mongodb insertion for isolate '{isolate_id}' completed")

                # todo
                # shutil.move(f"./{temp_new_sample_name}.log", f"/reports/{args.species}/{temp_new_sample_name}/{temp_new_sample_name}.log")

                # Removing the temporary working dir and the remaining files that were not kept
                # todo later shutil.rmtree(dir_temp) # 09-09 should i remove this though? we need the report html and tsv for bigsdb # 09-30 this removal was only after the report was moved somewhere else so justified (see reportmover.py in bigs)

    except Exception as exceptionmessage:
        _send_email(f"{os.path.basename(__file__)} fail on host {socket.gethostname()} for isolate {args.isolate['_id']}",
                    f"{exceptionmessage}\n{traceback.format_exc()}", mongo_config_data['mail'])

'''
To be ignored for mongodb, leaving the code in case useful later
'''
###
# Shell script for Cron
###

# #!/bin/bash
#
# export MODULEPATH=/etc/lmod/modules
# source /etc/profile.d/lmod.sh
#
# cd /temp/scratch
# export PYTHONPATH=/home/BIGSdb/automated-reanalysis
# source /home/BIGSdb/3.9PythonVenv/bin/activate
# for species in listeria neisseria stec mycobacterium salmonella
# do
#   python /home/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/reanalysis.py --host-url http://$HOSTNAME.sciensano.be --species $species --config /home/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/config.yml --threads 4
# done
