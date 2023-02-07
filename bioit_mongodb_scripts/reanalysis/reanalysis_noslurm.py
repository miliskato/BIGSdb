# export PYTHONPATH=/home/mikelchtermans/Bigsdb_mongodb/BIGSdb
# /home/mikelchtermans/3.9PythonVenv/bin/python3.9 /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/bioit_mongodb_scripts/reanalysis/reanalysis.py --species listeria --config /home/mikelchtermans/Bigsdb_mongodb/BIGSdb/bioit_mongodb_scripts/reanalysis/config.yml --threads 30 --pyvenvpythonpath /home/mikelchtermans/3.9PythonVenv/bin/python3.9
import argparse
import concurrent.futures
import datetime
import logging
import shutil
import socket
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, List, Dict, Optional

import yaml

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.mainmongo import MainMongo
from bioit_mongodb_scripts.reanalysis import MONGO_REANALYSIS_CONFIG
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, send_email

def _parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', type=str, required=True, choices=specieslist, help='Species to re-analyze')
    parser.add_argument('--threads', type=int, default=8, help='Number of threads to use in total')
    parser.add_argument('--analysis_arguments', nargs='+', required=False, help='analysis arguments stripped off --, e.g. "--analysis_arguments cgmlst mlst"')
    parser.add_argument('--maximal_analysis_date', type=str, required=True, help='YYYY-MM-DD')
    parser.add_argument('--minimal_analysis_date', type=str, required=True, help='YYYY-MM-DD')
    parser.add_argument('--alternate_connection_string', action='store_true', help=argparse.SUPPRESS)
    return parser.parse_args()


def __make_flagfilepath(isolatename: str, config: Dict[str, Any]) -> Path:
    """
    Returns the flagfile path based on the isolate name
    :param isolatename: name of the isolate
    :param config: config containing the flagfile directory path
    :return: Path
    """
    return Path(config['failsafe']['flag_dir']) / '.'.join([isolatename, config['failsafe']['flag_append']])


def _fail_safe_mechanism(isolatename: str, config: Dict[str, Any], reanalysis_outcome_dictionary: Dict[str, Any], tmp_dir: str) -> Optional[Dict[str, str]]:
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
            logging.warning(f"fail safe mechanism detects that the reanalysis for sample {isolatename} was started but didnt finish. Removing tmp_dir {tmp_dir_fail}.")
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

def _delete_flagfile(isolatename: str, config: Dict[str, Any], reanalysis_outcome_dictionary: dict) -> Optional[Dict[str, str]]:
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

def reanalysis_noslurm(species: str, maximal_analysis_date: str, minimal_analysis_date: str, threads: int = 8,
                       analysis_arguments: List[str] = None, alternate_connection_string: bool = False) -> None:
    """
    Main function
    See argparse function for variables and their requiredness
    :param species: commonly used bioit species name: either genus or specific like stec
    :param maximal_analysis_date: maximal analysis date of sample
    :param minimal_analysis_date: minimal analysis date of sample
    :param threads: number of total threads to use for reanalysis
    :param analysis_arguments: list of analysis arguments passed to the species specific pipeline
    :param alternate_connection_string: whether to use the alternate connection string for testing purposes
    :return: None
    """
    try:
        # Read the reanalysis config
        with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
            reanalysis_config = yaml.safe_load(handle)

        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Parse mongo config
        mongo_config_data = get_mongodb_config_data()

        # capture start_time
        start_time_reanalysis = datetime.datetime.utcnow()

        # Retrieve isolates that need to be re-analyzed
        mongoinit = MongoInitialisation(species, alternate_connection_string=alternate_connection_string)
        isolates_collection, old_isolateresults_collection, isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
        # query all the documents, # todo maybe do a projection as were only interested in _id, fastapath, vcfpath unless we also want db updates later (can also be projected)

        documents_list = [doc for doc in isolates_collection.find({'latest_analysis_date': {"$lt": maximal_analysis_date, "$gte": minimal_analysis_date}}, {"_id": 1, "fasta_path": 1, "vcf_path": 1, "report_directory": 1, "latest_analysis_date": 1})]
        logging.info(f"{len(documents_list)} isolates to be reanalyzed")

        # ! For testing, you can specify isolates manually here
        # documents_list = [{'_id':'Myco-DRR041783-ds', .......}]

        # Re-analyze the isolates (can be parallelized with a Snakemake workflow)
        # e.g. response_data['isolates'] : "isolates":["http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/3","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/4","http://bioit-bigs-dev.sciensano.be:5000/db/bigsdb_listeria_isolates/isolates/5"]
        def reanalyse_and_insert(isolate: Dict[str, str], threads_per_job: int = 2) -> Dict[str, str]:
            """
            Reanalyzes a given isolate dict (document from MongoDB)
            :param isolate: isolate dictionary from MongoDB
            :param threads_per_job: threads per sample
            :return: None
            """
            isolate_id = isolate['_id']
            reanalysis_outcome_dictionary = {'Outcome': 'Success', 'Isolate': isolate_id, 'Traceback': ''}
            try:
                isolate_id = isolate['_id']  # This line is duplicated so that it also falls in the try except
                logging.info(f"Starting reanalysis for {isolate_id}")

                # check if fasta path exists
                if Path(isolate['fasta_path']).is_file():
                    logging.info(f"Fasta file is real")
                    # todo check if fasta is actually fasta or not empty or?
                else:
                    logging.error('Invalid fastafilepath')
                    reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                    reanalysis_outcome_dictionary['Traceback'] = 'Invalid fastafilepath'
                    return reanalysis_outcome_dictionary

                temp_new_sample_name = '_'.join([isolate_id, str(datetime.date.today())])
                logging.info(f"new sample name: {temp_new_sample_name}")

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
                        f'--threads {threads_per_job}',
                        f'--sample-name {isolate_id}'
                    ])
                    command = Command(base_command)

                    # mycobacterium exception
                    if species == 'mycobacterium':
                        # if this vcf doesnt exist then pipeline will fail during execution and send a mail just like with any other error
                        # check if vcf path exists
                        # todo be sure that this vcf path is the unfiltered one
                        if Path(isolate['vcf_path']).is_file():
                            logging.info(f"vcf file is real")
                            command = Command(' '.join([base_command, f'--vcf-unfiltered {isolate["vcf_path"]}']))
                        else:
                            logging.info(f"No vcf file is provided, certain analyses can not be executed but will give an error if requested")
                    # run the command
                    command.run(dir_temp)
                    if command.returncode != 0:
                        reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                        reanalysis_outcome_dictionary['Traceback'] = f'Error executing automatic reanalysis pipeline on {species}, {isolate_id}, stderr: {command.stderr}'
                        return reanalysis_outcome_dictionary
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

                        # Adding the new sample version to the Mongo database
                        _delete_flagfile(isolate_id, reanalysis_config, reanalysis_outcome_dictionary)

                        # Create command insertion MongoDB
                        arguments = {'technical_id': isolate_id,
                                     'species': species,
                                     'results_type': 'reanalysis',
                                     'jsonfilepath': dir_out / 'report.json',
                                     'dontsend_email': True,
                                     'alternate_connection_string': alternate_connection_string}
                        # run the command
                        MainMongo(**arguments)
                        logging.info(f"Mongodb insertion for isolate '{isolate_id}' completed")
                        if alternate_connection_string is None:
                            try:
                                # shutil doesnt throw an error, but simply stops. Therefore it has to be put inside a try except
                                logging.info(
                                    f"executing: {dir_temp}/camel.log {isolate['report_directory']}/{temp_new_sample_name}.log")
                                shutil.move(f"{dir_temp}/camel.log", f"{isolate['report_directory']}/{temp_new_sample_name}.log")
                                logging.info(f"moving the camel log for isolate '{isolate_id}'")
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
                            logging.info(' '.join([
                                "executing: rsync -a",
                                f"{dir_temp}/{dir_out}/",
                                f"{isolate['report_directory']}/"
                            ]))
                            command.run(dir_out)
                            logging.info(f"merging the report directories of original and reanalysis for isolate '{isolate_id}'")
                            if command.returncode != 0:
                                reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                                reanalysis_outcome_dictionary['Traceback'] = f'Error merging reanalysis directory {dir_out} into output dir {isolate["report_directory"]} for automatic reanalysis pipeline on {species}, {isolate_id}, stderr: {command.stderr}'
                                return reanalysis_outcome_dictionary
                            else:
                                # Removing the temporary working dir and the remaining files that were not kept
                                shutil.rmtree(dir_temp)
                                logging.info(f"Temporary directory deletion for isolate '{isolate_id}' completed")
                        else:
                            # if testing purposes skip all of the above and only remove temp dir
                            shutil.rmtree(dir_temp)
                            logging.info(f"Temporary directory deletion for isolate '{isolate_id}' completed")
            except Exception as exceptionmessage:
                reanalysis_outcome_dictionary['Outcome'] = 'Fail'
                reanalysis_outcome_dictionary['Traceback'] = f"{exceptionmessage}\n{traceback.format_exc()}"
                return reanalysis_outcome_dictionary
            return reanalysis_outcome_dictionary
        if documents_list != []:
            with concurrent.futures.ThreadPoolExecutor(max_workers=int(threads / reanalysis_config['threads_per_job'])) as executor:
                futures = {executor.submit(
                    reanalyse_and_insert, **{'isolate': isolate, 'threads_per_job': reanalysis_config['threads_per_job']}):
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
                send_email(f"Ran from {start_time_reanalysis} to {end_time_reanalysis} for a total of {timedelta_reanalysis.days} days, {timedelta_reanalysis.seconds // 3600} hours, "
                           f"{(timedelta_reanalysis.seconds - (timedelta_reanalysis.seconds // 3600 * 3600)) // 60} minutes\n"
                           f"Succes Count: {succes_counter}\nFail Count: {fail_counter}\nFail Logs: {fail_logs}",
                           f"{Path(__file__).name} report on host {socket.gethostname()} at {datetime.datetime.utcnow()}")
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
    reanalysis_noslurm(args.species,
                       args.maximal_analysis_date,
                       args.minimal_analysis_date,
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
