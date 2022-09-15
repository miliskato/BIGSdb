import argparse
import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import shutil
import requests
import yaml
import psycopg2
import subprocess

from pymongo.write_concern import WriteConcern
from pymongo.read_concern import ReadConcern

from command.command import Command
from MongoDB.util.mongo_querying import Mongoquerying
from MongoDB.util.mongo_initialisation import Mongoinitialisation
from MongoDB.config import MONGO_CONFIG

import smtplib
from email.message import EmailMessage

def _parse_arguments() -> argparse.Namespace:
    """
    Parses the command line arguments.
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, help='Species to re-analyze')
    # parser.add_argument('--dir-fastq', type=Path, required=True, help='Directory containing FASTQ files')
    parser.add_argument('--config', type=Path, required=True, help='Configuration file')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use')
    parser.add_argument('--analysis_arguments', nargs='+', required=False, help='analysis arguments stripped off --, e.g. "--analysis_arguments cgmlst mlst"')
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

def send_email(subject: str, content: str, config: dict) -> None:
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

if __name__ == '__main__':
    # Configure stdout logging
    import sys
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse arguments
    args = _parse_arguments()

    # Read the reanalysis config
    with open(args.config, encoding='utf-8') as handle:
        config_data = yaml.safe_load(handle)

    # Parse config
    with open(MONGO_CONFIG, encoding='utf-8') as handle:
        mongo_config_data = yaml.safe_load(handle)

    # Retrieve isolates that need to be re-analyzed
    mongoinit = Mongoinitialisation()
    isolates_collection, isolateresults_collection, isolates_badqc_collection = mongoinit._initialise_collections(mongo_config_data, args.species)
    # query all the documents, # todo maybe do a projection as were only interested in _id, fastapath, vcfpath unless we also want db updates later (can also be projected)
    documents_list = [doc for doc in isolates_collection.find()]
    logging.info(f"{len(documents_list)} isolates to be reanalyzed")

    # ! For testing, you can specify isolates manually here
    # documents_list = [{'_id':'Myco-DRR041783-ds', .......}]

    # Re-analyze the isolates (can be parallelized with a Snakemake workflow)
    # e.g. response_data['isolates'] : "isolates":["http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/3","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/4","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/5"]
    for isolate in documents_list:
        isolate_id = isolate['_id']
        logging.info(f"Starting reanalysis for {isolate_id}")

        # check if fasta path exists
        import os
        if os.path.isfile(Path(isolate['fasta_path'])):
            logging.info(f"Fasta file is real")
            # todo check if fasta is actually fasta or?
        else:
            raise RuntimeError('Invalid fastafilepath')

        import datetime
        temp_new_sample_name = '_'.join([isolate_id, str(datetime.date.today())])
        logging.info(f"new sample name: {temp_new_sample_name}")
        # Get a temporary working directory
        with Path(tempfile.mkdtemp(None, 're_analysis_', config_data['temp_dir'])) as dir_temp:

            # Get the species-specific configuration
            config_species = config_data['species'][args.species]

            # Determine the output file paths
            dir_out = dir_temp / temp_new_sample_name
            dir_out.mkdir(exist_ok=True, parents=True)
            tsv_out = dir_out / 'report.tsv'
            html_out = dir_out / 'report.html'

            # Determine the options
            if args.analysis_arguments:
                available_options_list = config_species['options']
                accepted_options_list = []
                if args.species == 'mycobacterium' and 'vcf_path' not in isolate.keys():
                    available_options_list = config_species['options_without_vcf']
                for option in args.analysis_arguments:
                    option_reformatted = ''.join(['--', option])
                    if option_reformatted in available_options_list:
                        accepted_options_list.append(option_reformatted)
                    else:
                        raise RuntimeError(f'option {option_reformatted} is not a valid reanalysis option for species {args.species}')
            # if no specific analysis arguments are given, perform all analyses
            else:
                accepted_options_list = config_species['options']
                if args.species == 'mycobacterium' and 'vcf_path' not in isolate.keys():
                    accepted_options_list = config_species['options_without_vcf']

            # Create the command to re-analyze the datasets
            base_command = ' '.join([
                f"module load {config_species['lmod']};",
                f"{config_species['main_script']}",
                f'--fasta {isolate["fasta_path"]}',
                f'--output-dir {dir_out}',
                f"--output-html {html_out}",
                f'--output-tsv {tsv_out}',
                f'--working-dir {dir_temp}',
                *accepted_options_list,
                f'--threads {args.threads}'
            ])
            command = Command(base_command)

            # mycobacterium exception
            if args.species == 'mycobacterium':
                # if this vcf doesnt exist then pipeline will fail during execution and send a mail just like with any other error
                # check if vcf path exists
                import os
                # todo be sure that this vcf path is the unfiltered one
                if os.path.isfile(Path(isolate['vcf_path'])):
                    pass
                else:
                    raise RuntimeError('Invalid vcffilepath')
                command = Command(' '.join([base_command, f'--vcf-unfiltered {isolate["vcf_path"]}']))

            # run the command
            command.run(dir_temp)
            if command.returncode != 0:
                # if pipeline fails, send mail and continue to next sample
                send_email(f'Error executing automatic reanalysis pipeline on {args.species}, {isolate_id}', command.stderr, config_data['mail'])
                # raise RuntimeError(f"Error executing pipeline: {command.stderr}")
            else:
                logging.info(f"Re-analysis for isolate '{isolate_id}' completed")

            ## debugging purposes
            # if 1+1==3:
            #     continue
            # else:
            #     sample_name = 'S16BD02199'
            #     new_sample_name = 'S16BD02199_2022-09-14'
            #     uploader = 'mikeltestauto'
            #     dir_out = Path("/scratch/temp/re_analysis_pjx15wnq/S16BD02199_2022-09-14")

                # Adding the new sample version to the Mongo database
                handle = open(f"{temp_new_sample_name}.log", 'w+')
                def run_subprocess(custom_command):
                    result = subprocess.run(
                            custom_command,
                            stdout=handle,
                            stderr=handle,
                            shell=True,
                            executable='/bin/bash')
                    if result.returncode != 0:
                        send_email(
                            f'Error handling output of automatic reanalysis pipeline on {args.species}, {isolate_id}', f"look in file /reports/{args.species}/{temp_new_sample_name}/{temp_new_sample_name}.log", config_data['mail'])
                # moving the report
                # todo check if fasta files are same?
                run_subprocess(f"/home/mikelchtermans/PyCharmConnection/3.9PyCharmInterpreter/bin/python3.9 /home/mikelchtermans/Bigsdb_mongodb/MongoDB/mainmongo.py --results_type reanalysis --technical_id {isolate_id} --jsonfilepath {dir_out / 'report.json'} --species {args.species}")
                #shutil.move(f"./{temp_new_sample_name}.log", f"/reports/{args.species}/{temp_new_sample_name}/{temp_new_sample_name}.log")

                # Removing the temporary working dir and the remaining files that were not kept
                # todo later shutil.rmtree(dir_temp)

                ## debug
                print([doc for doc in isolates_collection.find()])
                #print([doc for doc in isolateresults_collection.find()])




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
