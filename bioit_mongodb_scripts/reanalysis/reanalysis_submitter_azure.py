#!/usr/bin/env python
import argparse
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Final, List

import azure.batch as batch
import azure.batch.models as batchmodels
import yaml
from azure.batch.models import (VirtualMachineConfiguration, BatchErrorException, TaskSchedulingPolicy,
                                TaskAddParameter,
                                NetworkConfiguration, OutputFile, OutputFileDestination, OutputFileUploadOptions,
                                OutputFileBlobContainerDestination)

from bioit_mongodb_scripts.util_azure.connect_azure import ConnectAzure

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.reanalysis import MONGO_REANALYSIS_CONFIG
from bioit_mongodb_scripts.reanalysis.reanalysis_triggers import TRIGGER_CONFIG
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data

BATCH_POOL_NAME: Final[str] = 'analysis_pool_focal'
BATCH_JOB_NAME_PREFIX: Final[str] = 'reanalysis_tasks_focal_'
AUTOSCALE_FORMULA = """$TargetLowPriorityNodes = max(0, $PendingTasks.GetSample(TimeInterval_Minute*5));\n$NodeDeallocationOption = taskcompletion;"""


def parse_arguments(specieslist: List[str]) -> argparse.Namespace:
    """
    Parses the command line arguments.
    !! If new arguments are added, Also add arguments/variables to main function/class!!
    :param specieslist: list of all the species choices
    :return: Parsed arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--species', required=False, type=str, choices=specieslist, default=specieslist,
                        nargs='+')  # this does allow for the same species multiple times but doesn't really matter, they're uniquely filtered using set() anyway
    parser.add_argument('--dtap', required=False, type=str, choices=['dev', 'test', 'acc', 'prod'],
                        default=['prod'],
                        nargs='+')  # this does allow for the same dtap multiple times but doesn't really matter, they're uniquely filtered using set() anyway
    return parser.parse_args()


def wrapper_loop_dtap_and_species(speciess: List[str], dtaps: List[str]) -> None:
    """
    Loops over all dtaps and species to launch the reanalyses accordingly.
    :param speciess: commonly used bioit species name: either genus or specific like stec
    :param dtaps: dev, test, acc, or prod
    :return: None
    """
    for dtap in set(dtaps):
        for species in set(speciess):
            BatchPipelinesReanalysis(species, dtap)


class BatchPipelinesReanalysis:
    """
    This class contains the functionalities check for dbupdates, and depending on the pathogen launch a different pipeline
    on a new VM according to the last analysis date of the sample and the last dbupdate of each argument. 
    The VM is stopped once the pipeline finished or fails but this is not handled in this class.
    The best-practices page concerning AB contains very useful information and is a must-read:
    https://learn.microsoft.com/en-us/azure/batch/best-practices
    According to this page, the best practice is to have few jobs with many tasks.
    A job can contain up to millions of tasks.
    Therefore for this system we will work with a single pool, containing a single job per pathogen with all tasks
    The class is auto-executable.
    """
    def __init__(self, species: str, dtap: str) -> None:
        """
        Initialises the class and runs the main function.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param dtap: dev, test, acc, or prod
        :return: None
        """
        self._species = species
        self._dtap = dtap

        # Read the reanalysis config
        with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
            self._reanalysis_config = yaml.safe_load(handle)
        # Connect to keyvault, batch account and storages
        self._connection_azure = ConnectAzure(self._dtap)
        self._batch_client = self._connection_azure.connect_to_batch_client()
        self._blob_service_client_input = self._connection_azure.connect_to_storages()
        self._batch_pipelines()

    def _batch_pipelines(self) -> None:
        """
        # Main function, creates the pool if it doesn't exist and then submits a job containing a single task
        which is the execution of the pipeline
        :return: None
        """
        self.__create_pool()
        # Create a new job:
        job_name = f"{BATCH_JOB_NAME_PREFIX}{self._species}"
        self.__create_job(job_name)

        if self._species not in ['sars_cov_2', 'influenza_a', 'influenza_b']:
            date_args_dict = self.__collect_database_update_dates()
            for maximal_analysis_date in date_args_dict:
                self.__launch_tasks(maximal_analysis_date, date_args_dict, job_name)
        else:
            self.__launch_tasks_viral(job_name)

    def __create_pool(self) -> None:
        """
        Creates a pool with a given specified name if it doesnt exist.
        :return: None
        """
        # Create a new pool if none exists
        logging.info(f"Checking pool {BATCH_POOL_NAME}'s existence")
        vm_size = self._connection_azure.get_secret_value('BATCH-VM-SIZE')
        node_agent_sku_id = 'batch.node.ubuntu 20.04'
        # listing popular images: az vm image list --output table # https://learn.microsoft.com/en-us/azure/virtual-machines/linux/cli-ps-findimage#list-popular-images
        # image_ref = ImageReference(publisher='Canonical', offer='0001-com-ubuntu-server-jammy', sku='22_04-lts-gen2')

        # Create an ImageReference which specifies the image from
        # Azure Compute Gallery to install on the nodes.
        image_ref = batchmodels.ImageReference(
            virtual_machine_image_id=self._connection_azure.get_secret_value('BATCH-IMAGE')
        )

        vm_config = VirtualMachineConfiguration(image_reference=image_ref, node_agent_sku_id=node_agent_sku_id)

        scheduling_policy = TaskSchedulingPolicy(node_fill_type='spread')

        network_configuration = NetworkConfiguration(
            subnet_id=self._connection_azure.get_secret_value('BATCH-SUBNET'))

        try:
            self._batch_client.pool.get(BATCH_POOL_NAME)
        except BatchErrorException as e:
            if e.response.status_code == 404:
                logging.info(f"Creating pool {BATCH_POOL_NAME}")
                # https://learn.microsoft.com/en-us/python/api/azure-batch/azure.batch.models.pooladdparameter?view=azure-python
                try:
                    self._batch_client.pool.add(batch.models.PoolAddParameter(
                        id=BATCH_POOL_NAME,
                        virtual_machine_configuration=vm_config,
                        vm_size=vm_size,
                        task_scheduling_policy=scheduling_policy,
                        # target_low_priority_nodes=0,  # can not be specified when using auto_scale
                        enable_auto_scale=True,
                        auto_scale_formula=AUTOSCALE_FORMULA,
                        auto_scale_evaluation_interval=timedelta(minutes=5),
                        task_slots_per_node=1,  # default is 1 but putting it here anyway in case they change the default
                        network_configuration=network_configuration
                    ))
                except:  # if the pool doesn't exist yet, and multiple samples are submitted at the same time; then a first sample will succeed and the rest will fail
                    logging.info(
                        f"Pool '{BATCH_POOL_NAME}' was likely created a fraction of time ago; continuing with job creation..")
                    pass

    def __create_job(self, job_name: str) -> None:
        """
        Creates a job with a species specific ID, associated with the specified pool.
        :param job_name: the Azure Batch job name
        :return: None
        """
        try:
            self._batch_client.job.get(job_name)
        except BatchErrorException as e:
            if e.response.status_code == 404:
                logging.info(f"Creating job {job_name}")
                job = batch.models.JobAddParameter(
                    id=job_name,
                    pool_info=batch.models.PoolInformation(pool_id=BATCH_POOL_NAME),
                    # job preparation task was attempted to be used to shuttle the input files but did not do anything without
                    # even providing an error, just kept on running indefinitely
                    # job_preparation_task=batch.models.JobPreparationTask(command_line=f'/bin/bash; -c "{install_azcopy_cmd}; {copy_command_1};{copy_command_2}"',
                    #                                                      wait_for_success=True),
                    # on_task_failure=,
                    # on_all_tasks_complete='terminateJob' #25/05 we never terminate the job anymore as it can scale up to millions of tasks
                )
                self._batch_client.job.add(job)

    def __collect_database_update_dates(self) -> Dict[str, List]:
        """
        Checks the local git versions/dates of the databases listed in the TRIGGER_CONFIG and dispatches jobs for all samples
        that do not have their results up to date according to the git versions
        :return: dictionary of last dbupdate dates grouped by date (key)
        """
        # Read the trigger config
        with open(TRIGGER_CONFIG, encoding='utf-8') as handle:
            trigger_config = yaml.safe_load(handle)

        # Configure stdout logging
        logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

        # Part 1: Query scheme last update dates and sort schemes by last update date
        date_scheme_dict = {}
        for scheme in trigger_config['species'][self._species]:
            logging.debug(f"scheme {scheme}")
            os.chdir(Path(trigger_config['species'][self._species][scheme]['dirdb']))
            # set git repo to safe repo
            subprocess.run(
                f"git config --global --add safe.directory {trigger_config['species'][self._species][scheme]['dirdb'].replace('/db', '/var/lib/.bioit_database')}",
                shell=True)
            # query_date
            gitlog = subprocess.run(
                "git log -n 1 --date=short -- . ':(exclude)scheme_metadata.json' ':(exclude)scheme_metadata.txt' ':(exclude)db_update_info.json' ':(exclude)db_metadata.txt'",
                shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
            scheme_last_update = re.findall("[0-9]{4}-[0-9]{2}-[0-9]{2}", gitlog)[0]
            trigger_config['species'][self._species][scheme]["last_update"] = scheme_last_update
            if scheme_last_update in date_scheme_dict:
                date_scheme_dict[scheme_last_update].append(
                    trigger_config['species'][self._species][scheme]['cmd_argument'])
            else:
                date_scheme_dict[scheme_last_update] = [
                    trigger_config['species'][self._species][scheme]['cmd_argument']]
        # e.g. date_scheme_dict: {'2022-10-02': ['mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation',
        #                         '2022-08-14': ['ncbi-amr'],
        #                         '2022-07-03': ['resfinder'],
        #                         '2020-06-24': ['virulencefinder', 'plasmidfinder'],
        #                         '2019-03-04': ['vfdb-core']}

        # Part 2: Recursively/hierarchically add all schemes with higher last update date to lower update date
        date_args_dict = {}
        for index, last_update in enumerate(sorted(date_scheme_dict)):
            date_args_dict[last_update] = date_scheme_dict[last_update]
            for last_update_later in sorted(date_scheme_dict)[index + 1:]:
                date_args_dict[last_update].extend(date_scheme_dict[last_update_later])
        # e.g. date_args_dict: {'2019-03-04': ['vfdb-core', 'virulencefinder', 'plasmidfinder', 'resfinder', 'ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2020-06-24': ['virulencefinder', 'plasmidfinder', 'resfinder', 'ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2022-07-03': ['resfinder', 'ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2022-08-14': ['ncbi-amr', 'mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation'],
        #                       '2022-10-02': ['mlst', 'cgmlst', 'pcr-serogroup', 'metal-detergent', 'typing-virulence', 'typing-amr', 'species-confirmation']}
        return date_args_dict

    def __launch_tasks(self, maximal_analysis_date: str, date_args_dict: Dict[str, List[str]], job_name: str) -> None:
        """
        Launches the Azure Batch tasks for all required samples for a given maximal_analysis_date
        :param maximal_analysis_date: key in the date_args_dict that we're currently looping over
        :param date_args_dict: the dictionary containing all dates and arguments
        :param job_name: the Azure Batch job name
        :return: None
        """
        ordered_dates_list = sorted(date_args_dict)
        index_date_in_list = ordered_dates_list.index(maximal_analysis_date)
        minimal_analysis_date = ordered_dates_list[index_date_in_list - 1] if index_date_in_list != 0 else '1970-01-01'
        logging.info(
            f"Submitting reanalysis for samples older than {maximal_analysis_date} and younger than {minimal_analysis_date} with arguments: {date_args_dict[maximal_analysis_date]} for {self._species}_{self._dtap}")
        # Retrieve isolates that need to be re-analyzed
        mongoinit = MongoInitialisation(self._species,
                                        alternate_connection_string=self._connection_azure.get_secret_value(
                                            'MONGODB-CONNECTION-STRING'),
                                        alternate_dtap=self._dtap)
        isolates_collection, old_isolateresults_collection, \
            isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
        # query all the documents as a projection
        documents_list = [doc for doc in
                          isolates_collection.find({'latest_analysis_date': {"$lt": maximal_analysis_date,
                                                                             "$gte": minimal_analysis_date}},
                                                   {"_id": 1, "fasta_path": 1, "vcf_path": 1, "vcf_path_unfiltered": 1,
                                                    "original_input_format": 1, "latest_analysis_date": 1,
                                                    "report_directory": 1, "results.isolates_id": 1}
                                                   )
                          ]
        logging.info(f"{len(documents_list)} isolates to be reanalyzed for {self._species}_{self._dtap}")
        for mongodb_document in documents_list:
            # Create a new task to execute a command on the VM
            task_name = f"{mongodb_document['results']['isolates_id'][:43]}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            command = self.___build_command(task_name, date_args_dict[maximal_analysis_date], mongodb_document)
            self.___create_task(job_name, task_name, command)
        logging.info(
            f"Reanalysis submission for samples older than {maximal_analysis_date} with arguments: {date_args_dict[maximal_analysis_date]} completed")

    def __launch_tasks_viral(self, job_name: str) -> None:
        """
        Launches the Azure Batch tasks for all viral samples
        :param job_name: the Azure Batch job name
        :return: None
        """
        # Retrieve isolates that need to be re-analyzed
        mongoinit = MongoInitialisation(self._species,
                                        alternate_connection_string=self._connection_azure.get_secret_value(
                                            'MONGODB-CONNECTION-STRING'),
                                        alternate_dtap=self._dtap)
        isolates_collection, old_isolateresults_collection, \
            isolates_badqc_collection, isolates_resequencing_collection = mongoinit.initialise_collections()
        # query all the documents as a projection
        fields_to_retrieve = {
            "_id": 1,
            "fasta_path": 1,
            "vcf_path": 1,
            "vcf_path_unfiltered": 1,
            "original_input_format": 1,
            "latest_analysis_date": 1,
            "report_directory": 1,
            "results.isolates_id": 1
        }

        documents_list = list(isolates_collection.find({}, fields_to_retrieve))

        logging.info(f"{len(documents_list)} isolates to be reanalyzed for {self._species}_{self._dtap}")
        analysis_arguments = [argument.replace('--', '') for argument in
                              self._reanalysis_config['species'][self._species]['options']]
        for mongodb_document in documents_list:
            # Create a new task to execute a command on the VM
            task_name = f"{mongodb_document['results']['isolates_id'][:43]}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            command = self.___build_command(task_name, analysis_arguments, mongodb_document)
            self.___create_task(job_name, task_name, command)
        logging.info(
            f"Reanalysis submission for {self._species} samples with arguments: {analysis_arguments} completed")

    def ___create_task(self, job_name: str, task_name: str, command: str) -> None:
        """
        Creates a task in the previously created job with the same name as the created job.
        Only a single task is submitted per job because all our jobs/tasks arrive separately
        and should be executed on a single VM anyway.
        :param job_name: the Azure Batch job name
        :param task_name: the Azure Batch task name
        :param command: the full shell command to be executed on the Azure spot instance in Azure Batch
        :return: None
        """
        logging.info(f"Creating task {task_name} in job {job_name}")
        INPUT_STORAGE_ACCOUNT_NAME = f"dlsweu{self._dtap}processing"
        task = TaskAddParameter(
            id=task_name,  # (task name == job name) because  we are only using one task per job
            command_line=command,
            resource_files=[],
            user_identity=None,
            environment_settings=None,
            multi_instance_settings=None,
            constraints=None,
            output_files=[OutputFile(
                file_pattern="../stderr.txt",
                destination=OutputFileDestination(
                    container=OutputFileBlobContainerDestination(
                        container_url=f"https://{INPUT_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/batch-logs?{self._connection_azure.sas_token_blobstorage_input}",
                        path=f"{BATCH_POOL_NAME}/{job_name}/{task_name}_stderr.txt"
                    )
                ),
                upload_options=OutputFileUploadOptions(
                    upload_condition="taskfailure"
                    # task failure means an external failure, but
                    # because of "set -o errexit" in the command, a camel failure can also be detected
                )
            )]

        )
        self._batch_client.task.add(job_name, task)

    def ___build_command(self, task_name: str, analysis_arguments: List[str], mongodb_document: Dict[str, Any]) -> str:
        """
        Builds the pathogen specific command
        :param task_name: the Azure Batch task name
        :param analysis_arguments: the list of analysis arguments to use with the corresponding to be reanalysed mongodb doc.
        :param mongodb_document: The mongodb document of the to be reanalyzed sample
        :return: command
        """
        report_dir = f'$AZ_BATCH_TASK_DIR/{self._dtap}/report_dirs/reanalysis/{self._species}/{task_name}'
        working_dir = f'$AZ_BATCH_TASK_DIR/{self._dtap}/working_dirs/reanalysis/{self._species}/{task_name}_working'
        results_dir = mongodb_document['report_directory']
        # pre command to load lmod and to stop commands upon failure (set -o errexit)
        pre_command = 'export MODULEPATH=/etc/lmod/modules; source /etc/profile.d/lmod.sh'
        trap_command = (f'trap \'mkdir -p /scratch/scratch/{self._dtap}/errors/reanalysis/{self._species}/{task_name}; '
                        f'if test -e {working_dir}; then cp -r {working_dir} /scratch/scratch/{self._dtap}/errors/reanalysis/{self._species}/{task_name}; rm -r {working_dir}; fi; '
                        f'if test -e {report_dir}; then cp -r {report_dir} /scratch/scratch/{self._dtap}/errors/reanalysis/{self._species}/{task_name}; rm -r {report_dir}; fi; '
                        f'exit 1\' ERR')
        # Create the command to re-analyze the datasets
        config_species = self._reanalysis_config['species'][self._species]
        isolate_id = mongodb_document['results']['isolates_id']
        reference_genome_size = int(1.5*self._reanalysis_config['reference_genome_size'][self._species])
        size_command = f"assembly_size=$(stat -c%s {mongodb_document['fasta_path']}); if [ $assembly_size -gt {reference_genome_size} ]; then echo \'Error: The size of the assembly is larger than 1.5 times the reference genome size of {self._species}.\' >&2; exit 1; fi"
        """
        We're creating the report dir before the smk pipe does it, because then if the smk fails for whatever reason,
        the stderr.txt and stdout.txt files can still be copied to the report_dir in the post_command
        """
        base_command = ' '.join([
            f"module load {config_species['lmod']};",
            'pipeline_hash=$(git --git-dir=$PYTHONPATH/.git rev-parse --short=10 HEAD);',  # need to be double "
            f"mkdir -p {working_dir};",
            f"cd {working_dir};"
            f"{config_species['main_script']} ",
            f"--fasta {mongodb_document['fasta_path']} ",
            '--detection-method blast' if self._species not in ['sars_cov_2', 'influenza_a', 'influenza_b'] else '',
            '--library NexteraPE',  # should be changed in the future?
            f'--working-dir {working_dir}',
            f'--output-dir {report_dir}',
            f"--output-html {report_dir}/report.html",
            f'--output-tsv {report_dir}/report.tsv',
            ' '.join([f"--{x}" for x in analysis_arguments]),
            '--threads 2',
            f'--sample-name {isolate_id}',
            f"--reanalysis-original-input {mongodb_document['original_input_format']}"
        ])
        if self._species == 'mycobacterium' and mongodb_document['original_input_format'] != 'fasta':
            base_command += f' --vcf-unfiltered {mongodb_document["vcf_path_unfiltered"]}' if mongodb_document.get(
                "vcf_path_unfiltered") else ''
        unload_command = f"module unload {config_species['lmod']}"
        config_mongodb = self._reanalysis_config['mongodb']
        report_command = ' '.join([
            f"module load {config_mongodb['lmod']};",
            f"{config_mongodb['report_script']}",
            f"--base-html {results_dir}/report.html",
            f"--updated-html {report_dir}/report.html",
            f"--species {self._species}",
            f"--analysis-arguments {' '.join(analysis_arguments)}"
        ])
        # Copy the stderr and stdout files from the temporary working dir to the fileshare because they
        # might contain more information than the camel.log
        post_command = f'cp $AZ_BATCH_TASK_DIR/std*.txt {report_dir}/'
        # Check if report.html exists, if it does, remove working directory to clean up and
        # stderr + stdout because they're not necessary
        cleanup_command = f"if test -e {report_dir}/report.html ; then rm -r {working_dir}; rm {report_dir}/std*.txt; fi; cd $AZ_BATCH_TASK_DIR; rsync -a --no-p --no-o --no-g {report_dir}/ {results_dir}/; rm {results_dir}/camel.log; rm -r {report_dir}"
        # the cd before rsync is necessary because else it will throw the error: rsync: getcwd(): No such file or directory (2)
        lockfile = f"/scratch/scratch/{self._dtap}/mainmongo_{self._species}.lockfile"
        mongodb_command = ' '.join([
            f"start_time=$(date +%s); while ! /usr/bin/flock -n {lockfile} true && (( $(date +%s) - start_time < 3600 )); do sleep 1; done;",
            f"/usr/bin/flock -u {lockfile}",
            f"{config_mongodb['main_script']}",
            "--results_type reanalysis",
            f"--species {self._species}",
            f"--technical_id {isolate_id}",
            "--pipeline_hash $pipeline_hash",
            f"--jsonfilepath {results_dir}/report.json",
            "--dont_send_email",
            f"--alternate_dtap {self._dtap}",
            f"--alternate_connection_string {self._connection_azure.get_secret_value('MONGODB-CONNECTION-STRING')}"
        ])
        task_command = f'/bin/bash -c "{pre_command}; {trap_command}; {size_command}; {base_command}; {unload_command}; {report_command}; {post_command}; {cleanup_command}; {mongodb_command}"'
        return task_command


if __name__ == '__main__':
    # Configure stdout logging
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # Parse config
    mongo_config_data = get_mongodb_config_data()

    # Parse arguments
    args = parse_arguments(mongo_config_data['species'])

    # run main
    wrapper_loop_dtap_and_species(args.species, args.dtap)
