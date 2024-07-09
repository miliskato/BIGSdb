# /home/mikelchtermans/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/bioit_mongodb_scripts/reanalysis/reanalysis.py --species listeria --config /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/bioit_mongodb_scripts/reanalysis/config.yml --threads 30 --pyvenvpythonpath /home/mikelchtermans/3.9PythonVenv/bin/python3.9
import argparse
import datetime
import json
import logging
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Optional

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.mainmongo import MainMongo
from bioit_mongodb_scripts.reanalysis import MONGO_REANALYSIS_CONFIG
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data


def _parse_arguments(specieslist: list) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, choices=specieslist, help='Species to re-analyze')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use')
    parser.add_argument('--analysis_arguments', nargs='+', required=False,
                        help='analysis arguments stripped off --, e.g. "--analysis_arguments cgmlst mlst"')
    parser.add_argument('--isolate', type=json.loads, required=True)
    parser.add_argument('--alternate_connection_string', action='store_true', help=argparse.SUPPRESS)
    return parser.parse_args()


def __make_flagfilepath(isolatename: str, config: dict) -> Path:
    """
    Returns the flagfile path based on the isolate name
    :param isolatename: name of the isolate
    :param config: config containing the flagfile directory path
    :return: Path
    """
    return Path(config['failsafe']['flag_dir']) / '.'.join([isolatename, config['failsafe']['flag_append']])


def _fail_safe_mechanism(isolatename: str, config: dict, reanalysis_outcome_dictionary: dict, tmp_dir: str) -> Optional[Dict[str, str]]:
    """
    Creates a flagfile containing the temporary dictionary if the file doesnt exist, if it does, remove the previous temporary directory, the file, and recreate the file
    :param isolatename: name of the isolate
    :param config: config containing the flagfile directory path
    :param reanalysis_outcome_dictionary: config containing the reanalysis outcome
    :param tmp_dir: temporary working dir
    :return: None
    """
    try:
        if not Path(config['failsafe']['flag_dir']).is_dir():
            Path(config['failsafe']['flag_dir']).mkdir()
            Path(config['failsafe']['flag_dir']).chmod(0o777)
        flagfilepath = __make_flagfilepath(isolatename, config)
        if flagfilepath.is_file():
            with flagfilepath.open('r') as handle:
                tmp_dir_fail = handle.readlines()[0]
            logging.warning(f"fail safe mechanism detects that the reanalysis for sample {isolatename} was started but did not finish. Removing tmp_dir {tmp_dir_fail}.")
            shutil.rmtree(Path(tmp_dir_fail))
            # remove flagfilepath with wrong tmp dir in case reanalysis fails again
            flagfilepath.unlink()
        with flagfilepath.open('w') as handle:
            handle.write(tmp_dir)
        flagfilepath.chmod(0o777)
        logging.info(f"flagfilepath {flagfilepath}")
    except Exception as exceptionmessage:
        reanalysis_outcome_dictionary['Outcome'] = 'Fail'
        reanalysis_outcome_dictionary['Traceback'] = f"reanalysis fail safe mechanism fail: {exceptionmessage}\n{traceback.format_exc()}"
        return reanalysis_outcome_dictionary

def _delete_flagfile(isolatename: str, config: dict, reanalysis_outcome_dictionary: dict) -> Optional[Dict[str, str]]:
    """
    Removes the flagfile
    :param isolatename: name of the isolate
    :param config: config containing the flagfile directory path
    :param reanalysis_outcome_dictionary: config containing the reanalysis outcome
    :return: None
    """
    flagfilepath = __make_flagfilepath(isolatename, config)
    try:
        flagfilepath.unlink()
    except Exception:
        reanalysis_outcome_dictionary['Outcome'] = 'Fail'
        reanalysis_outcome_dictionary['Traceback'] = f"Could not remove flag file {flagfilepath}"
        return reanalysis_outcome_dictionary

def reanalysis_slurm(species: str, isolate: json.loads, threads: int = 8, analysis_arguments: list = None, alternate_connection_string: bool = False) -> Dict[str, str]:
    """
    Main function
    See argparse function for variables and their requiredness
    :param species:
    :param isolate:
    :param threads:
    :param analysis_arguments:
    :param alternate_connection_string:
    :return:
    """
    isolate_id = isolate['_id']
    reanalysis_outcome_dictionary = {'Outcome': 'Success', 'Isolate': isolate_id, 'Traceback': ''}
    try:
        # Read the reanalysis config
        with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
            reanalysis_config = yaml.safe_load(handle)

        # Configure stdout # logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Parse config
        mongo_config_data = get_mongodb_config_data()

        # ! For testing, you can specify isolates manually here
        # documents_list = [{'_id':'Myco-DRR041783-ds', .......}]

        # Re-analyze the isolates (can be parallelized with a Snakemake workflow)
        # e.g. response_data['isolates'] : "isolates":["http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/3","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/4","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/5"]
        isolate_id = isolate['_id']  # This line is duplicated so that it also falls in the try except
        # logging.info(f"Starting reanalysis for {isolate_id}")

        # check if fasta path exists
        if Path(isolate['fasta_path']).is_file():
            # logging.info(f"Fasta file is real")
            # todo check if fasta is actually fasta or not empty or?
            pass
        else:
            # logging.error('Invalid fastafilepath')
            reanalysis_outcome_dictionary['Outcome'] = 'Fail'
            reanalysis_outcome_dictionary['Traceback'] = 'Invalid fastafilepath'
            return reanalysis_outcome_dictionary

        temp_new_sample_name = '_'.join([isolate_id, str(datetime.date.today())])
        # logging.info(f"new sample name: {temp_new_sample_name}")

        # Get a temporary working directory
        with Path(tempfile.mkdtemp(None, 're_analysis_', mongo_config_data['temp_dir'])) as dir_temp:

            # initialise fail-safe mechanism
            _fail_safe_mechanism(isolate_id, reanalysis_config, reanalysis_outcome_dictionary, str(dir_temp))

            # Get the species-specific configuration
            config_species = reanalysis_config['species'][species]

            # Determine the output file paths
            dir_out = dir_temp / temp_new_sample_name
            dir_out.mkdir(exist_ok=True, parents=True)
            tsv_out = dir_out / 'report.tsv'
            html_out = dir_out / 'report.html'

            # Determine the options
            if analysis_arguments:
                available_options_list = config_species['options']
                accepted_options_list = []
                if species == 'mycobacterium' and 'vcf_path' not in isolate:
                    available_options_list = config_species['options_without_vcf']
                for option in analysis_arguments:
                    option_reformatted = ''.join(['--', option])
                    if option_reformatted in available_options_list:
                        accepted_options_list.append(option_reformatted)
                    else:
                        reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                        reanalysis_outcome_dictionary['Traceback'] = f'option {option_reformatted} is not a valid reanalysis option for species {species}'
                        return reanalysis_outcome_dictionary
            # if no specific analysis arguments are given, perform all analyses
            else:
                accepted_options_list = config_species['options']
                if species == 'mycobacterium' and 'vcf_path' not in isolate:
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
                f'--threads {threads}',
                f'--sample-name {isolate_id}'
            ])
            command = Command(base_command)

            # mycobacterium exception
            if species == 'mycobacterium':
                # if this vcf doesnt exist then pipeline will fail during execution and send a mail just like with any other error
                # check if vcf path exists
                # todo be sure that this vcf path is the unfiltered one
                if Path(isolate['vcf_path']).is_file():
                    # logging.info(f"vcf file is real")
                    command = Command(' '.join([base_command, f'--vcf-unfiltered {isolate["vcf_path"]}']))
                else:
                    # logging.info(f"No vcf file is provided, certain analyses can not be executed but will give an error if requested")
                    pass
            # run the command
            command.run(dir_temp)
            if command.returncode != 0:
                # if pipeline fails, send mail and continue to next sample, dont raise error # Since the mailbomb, do raise an error
                reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                reanalysis_outcome_dictionary['Traceback'] = f'Error executing automatic reanalysis pipeline on {species}, {isolate_id}, stderr: {command.stderr}'
                return reanalysis_outcome_dictionary
            else:
                # logging.info(f"Re-analysis for isolate '{isolate_id}' completed")

                # # debugging purposes
                # if 1+1==3:
                #     continue
                # else:
                #     sample_name = 'S16BD02199'
                #     new_sample_name = 'S16BD02199_2022-09-14'
                #     uploader = 'mikeltestauto'
                #     dir_out = Path("/scratch/temp/re_analysis_pjx15wnq/S16BD02199_2022-09-14")

                _delete_flagfile(isolate_id, reanalysis_config, reanalysis_outcome_dictionary)

                # Create command insertion MongoDB
                arguments = {'technical_id': isolate_id,
                             'species': species,
                             'results_type': 'reanalysis',
                             'jsonfilepath': dir_out / 'report.json',
                             'dont_send_email': True,
                             'alternate_connection_string': alternate_connection_string}
                # run the command
                MainMongo(**arguments)
                # logging.info(f"Mongodb insertion for isolate '{isolate_id}' completed")
                if alternate_connection_string is False:
                    try:
                        # shutil doesnt throw an error, but simply stops. Therefore it has to be put inside a try except
                        # logging.info(f"executing: {dir_temp}/camel.log {isolate['report_directory']}/{temp_new_sample_name}.log")
                        shutil.move(f"{dir_temp}/camel.log",
                                    f"{isolate['report_directory']}/{temp_new_sample_name}.log")
                        # logging.info(f"moving the camel log for isolate '{isolate_id}'")
                    except Exception:
                        reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                        reanalysis_outcome_dictionary['Traceback'] = f"shutil failed to move camel log {dir_temp}/camel.log to {isolate['report_directory']}/{temp_new_sample_name}.log, stderr: {command.stderr}"
                        return reanalysis_outcome_dictionary

                    report_dir_merging_cmd = ' '.join([
                        "rsync -a",
                        f"{dir_out}/",
                        f"{isolate['report_directory']}/"
                    ])
                    command = Command(report_dir_merging_cmd)
                    # run the command
                    # logging.info(' '.join([
                    #     "executing: rsync -a",
                    #     f"{dir_temp}/{dir_out}/",
                    #     f"{isolate['report_directory']}/"
                    # ]))
                    command.run(dir_out)
                    # logging.info(f"merging the report directories of original and reanalysis for isolate '{isolate_id}'")
                    if command.returncode != 0:
                        reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                        reanalysis_outcome_dictionary['Traceback'] = f'Error merging reanalysis directory {dir_out} into output dir {isolate["report_directory"]} for automatic reanalysis pipeline on {species}, {isolate_id}, stderr: {command.stderr}'
                        return reanalysis_outcome_dictionary
                    else:
                        # Removing the temporary working dir and the remaining files that were not kept
                        shutil.rmtree(dir_temp)
                        # logging.info(f"Temporary directory deletion for isolate '{isolate_id}' completed")
                else:
                    # if testing purposes skip all of the above and only remove temp dir
                    shutil.rmtree(dir_temp)
                    # logging.info(f"Temporary directory deletion for isolate '{isolate_id}' completed")
    except Exception as exceptionmessage:
        reanalysis_outcome_dictionary['Outcome'] = 'Fail'
        reanalysis_outcome_dictionary['Traceback'] = f"{exceptionmessage}\n{traceback.format_exc()}"
        return reanalysis_outcome_dictionary
    return reanalysis_outcome_dictionary


if __name__ == '__main__':

    # Read the reanalysis config
    with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
        reanalysis_config = yaml.safe_load(handle)

    # Parse arguments
    args = _parse_arguments(list(reanalysis_config['species']))

    # run main
    reanalysis_slurm(args.species,
                     args.isolate,
                     threads=args.threads,
                     analysis_arguments=(args.analysis_arguments if args.analysis_arguments else None),
                     alternate_connection_string=(True if args.alternate_connection_string else False))

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
# export PYTHONPATH=/home/bigsdb/BIGSdb/automated-reanalysis
# source /home/bigsdb/BIGSdb/3.9PythonVenv/bin/activate
# for species in listeria neisseria stec mycobacterium salmonella
# do
#   python /home/bigsdb/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/reanalysis.py --host-url http://$HOSTNAME.sciensano.be --species $species --config /home/bigsdb/BIGSdb/automated-reanalysis/camel/scripts/reanalysis/config.yml --threads 4
# done
