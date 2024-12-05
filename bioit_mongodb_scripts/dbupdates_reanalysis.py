import logging
import os
import socket
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path

from azure import batch
from azure.monitor.ingestion import LogsIngestionClient

from bioit_mongodb_scripts.reanalysis import MONGO_REANALYSIS_CONFIG
from bioit_mongodb_scripts.reanalysis.reanalysis_submitter_azure import BatchPipelinesReanalysis
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data
from bioit_mongodb_scripts.util_azure.connect_azure import ConnectAzure
from bioit_mongodb_scripts.util_azure.tempid_replacer_azure import TempidReplacerAzure

REMOVE_LOGS = 'find /var/log/dbupdate-logs/ -maxdepth 1 -mtime +28 -exec rm -rf {} \; 2>/dev/null'
DBUPDATES = 'export DB_UPD_ROOT="/opt/db_update"; export XDG_CACHE_HOME="/var/cache/dbupdate_cache"; /opt/db_update/dbupdate/scripts/bash/update_weekly.sh >> /var/log/dbupdate-logs/$(date +"%Y_%m_%d_%H-%M-%S")_updatelog.txt 2>&1'
DEALLOCATE_VM = 'az login --identity; az vm deallocate -n $(hostname) -g $(curl -s -H Metadata:true --noproxy "*" "http://169.254.169.254/metadata/instance?api-version=2021-02-01" | python3 -c \'import sys, json; print(json.load(sys.stdin)["compute"]["resourceGroupName"])\')'


class DbUpdatesReanalysis:
    """
    This class disables jobs in the batch accounts of the given environments, checks whether database updates can be
    carried out, executes the database updates, enables jobs again, launches the reanalysis and eventually
    deallocates the dbupdates VM.
    """

    def __init__(self, environment: str) -> None:
        """
        Initialises the class, connects to the keyvaults and batch accounts associated with the environment
        and executes the main functions.
        :param environment: dt or ap
        :return: None
        """
        try:
            filename_log = f"/var/log/dbupdate-logs/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_log.txt"
            logging.basicConfig(filename=filename_log, filemode='w', level=logging.DEBUG,
                                format='%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
            self._environment = environment
            # Read the reanalysis config
            with open(MONGO_REANALYSIS_CONFIG, encoding='utf-8') as handle:
                self._reanalysis_config = yaml.safe_load(handle)
            self._connection_azure_1, self._connection_azure_2 = self._connect_azure()
            self._batch_client_1 = self._connection_azure_1.connect_to_batch_client()
            self._batch_client_2 = self._connection_azure_2.connect_to_batch_client()
            self._disable_batch_jobs(self._batch_client_1)
            self._disable_batch_jobs(self._batch_client_2)
            self._execute_dbupdates()
            self._enable_batch_jobs(self._batch_client_1)
            self._enable_batch_jobs(self._batch_client_2)
            self._execute_reanalysis()
        except Exception as e:
            self._enable_batch_jobs(self._batch_client_1)
            self._enable_batch_jobs(self._batch_client_2)
            logging.error(f"An exception occurred during the database updates and the automated reanalysis: {e}")
            message_log = "An error occurred during the database updates and launching of the reanalysis"
            self._send_log_entry(level="Error", exception_message=str(e), message=message_log,
                                 stream_name="Custom-DbupdatesReanalysis_CL")
        finally:
            self._execute_command(DEALLOCATE_VM)

    def _connect_azure(self) -> tuple[ConnectAzure, ConnectAzure]:
        """
        Connects to the keyvaults of the environments (dt or ap).
        return: connections to the keyvaults
        """
        if self._environment == 'dt':
            connection_azure_1 = ConnectAzure("dev")
            connection_azure_2 = ConnectAzure("test")
        elif self._environment == 'ap':
            connection_azure_1 = ConnectAzure("acc")
            connection_azure_2 = ConnectAzure("prod")
        else:
            raise Exception(f"Environment ({self._environment}) is not dt or ap")
        return connection_azure_1, connection_azure_2

    def _execute_dbupdates(self) -> None:
        """
        Checks whether the database updates can be carried out, removes logs older than 4 weeks, executes the
        database updates and executes the tempid replacer.
        :return: None
        """
        self.__check_dbupdates()
        self._execute_command(REMOVE_LOGS)
        self._execute_command(DBUPDATES)
        self.__execute_tempid_replacer()

    def __check_dbupdates(self, max_hours: int = 10, sleep_minutes: int = 20) -> None:
        """
        Checks whether the database updates can be carried out (no tasks running). If not, it keeps regularly checking
        whether the database updates can be carried out. If the database updates can't be carried out after a maximum
        time, it will raise an exception.
        :param max_hours: How many hours it will maximally wait until raising an exception
        :param sleep_minutes: After how many minutes it will check again the status of the tasks
        """
        start_time = datetime.now()
        while datetime.now() - start_time < timedelta(hours=max_hours):
            tasks_status_1 = self.__get_task_status(self._batch_client_1)
            tasks_status_2 = self.__get_task_status(self._batch_client_2)
            combined_status = tasks_status_1 + tasks_status_2
            if any(status == "running" for status in combined_status):
                logging.info("Still tasks running, database updates can't be carried out")
                time.sleep(sleep_minutes * 60)
            else:
                logging.info("Database updates can be carried out")
                break  # Break out of the loop if no tasks are running
        else:
            raise Exception(f"Maximum waiting time ({max_hours} hours) has passed, database updates can't be carried out")

    def __execute_tempid_replacer(self) -> None:
        """
        Executes the tempid replacer azure script.
        :return: None
        """
        for species in self._reanalysis_config['species'].keys():
            if self._environment == 'dt':
                TempidReplacerAzure(species, "dev")
                TempidReplacerAzure(species, "test")
            if self._environment == 'ap':
                TempidReplacerAzure(species, "acc")
                TempidReplacerAzure(species, "prod")

    def _execute_reanalysis(self) -> None:
        """
        Executes the reanalysis script.
        :return: None
        """
        for species in self._reanalysis_config['species'].keys():
            if self._environment == 'dt':
                BatchPipelinesReanalysis(species, "dev")
                BatchPipelinesReanalysis(species, "test")
            if self._environment == 'ap':
                BatchPipelinesReanalysis(species, "acc")
                BatchPipelinesReanalysis(species, "prod")

    @staticmethod
    def _disable_batch_jobs(batch_client: batch.BatchServiceClient, retries: int = 3, timeout: int = 60 * 5, disable_tasks: str = "wait") -> None:
        """
        Disables all the jobs of a specific batch account. Default of disable tasks is wait which means that currently
        running tasks are allowed to complete, while newly added tasks are queued.
        :param batch_client: Batch account
        :param retries: Number of retries
        :param timeout: Waiting time until trying again
        :param disable_tasks: requeue, terminate or wait
        :return: None
        """
        for job in batch_client.job.list():
            job_disabled = False
            for retry in range(retries):
                try:
                    if job.state not in ('disabled', 'disabling'):
                        batch_client.job.disable(job.id, disable_tasks)
                        logging.info(f"Job {job.id} has been successfully disabled.")
                        job_disabled = True
                        break
                    else:
                        logging.info(f"Job {job.id} was already disabled.")
                        job_disabled = True
                        break
                except Exception as e:
                    message_log = f"Job {job.id} could not be disabled at try {retry}: {e}."
                    logging.info(message_log)
                    time.sleep(timeout)
            if not job_disabled:
                raise Exception(f"Job {job.id} could not be disabled")

    def _enable_batch_jobs(self, batch_client: batch.BatchServiceClient, retries: int = 3, timeout: int = 60 * 5) -> None:
        """
        Enables all the jobs of a specific batch account.
        :param batch_client: Batch account
        :param retries: Number of retries
        :param timeout: Waiting time until trying again
        :return: None
        """
        for job in batch_client.job.list():
            job_enabled = False
            for retry in range(retries):
                try:
                    if job.state not in ('active', 'enabling'):
                        batch_client.job.enable(job.id)
                        logging.info(f"Job {job.id} has been successfully enabled.")
                        job_enabled = True
                        break
                    else:
                        logging.info(f"Job {job.id} was already enabled.")
                        job_enabled = True
                        break
                except Exception as e:
                    message_log = f"Job {job.id} could not be enabled at try {retry}: {e}."
                    logging.warning(message_log)
                    time.sleep(timeout)
            if not job_enabled:
                message_log = f"Job {job.id} could not be enabled"
                self._send_log_entry(level="Error", exception_message=message_log, message=message_log,
                                     stream_name="Custom-DbupdatesReanalysis_CL")

    @staticmethod
    def __get_task_status(batch_client: batch.BatchServiceClient) -> list:
        """
        Gets the status of all the tasks for all the jobs of a specific batch account.
        :param batch_client: batch account
        :return: list with the statuses of all tasks of a specific batch account
        """
        tasks_status = []
        for job in batch_client.job.list():
            # Get the list of tasks for the current job
            tasks = batch_client.task.list(job.id)
            for task in tasks:
                task_status = task.state
                tasks_status.append(task_status)
        return tasks_status

    def _send_log_entry(self, level: str, exception_message: str, message: str, stream_name: str):
        """
        Sends a log to the log analytics space.
        param level: importance of the log
        param exception_message: exception message
        param message: information message
        param stream_name: Table to which the log is written
        """
        endpoint = self._connection_azure_1.get_secret_value('DATA-COLLECTION-ENDPOINT-DBUPDATES')
        client = LogsIngestionClient(endpoint=endpoint, credential=self._connection_azure_1.credential)
        rule_id = self._connection_azure_1.get_secret_value('DBUPDATES-REANALYSIS-RULE-ID')

        time_generated = datetime.now().isoformat()
        body = [{
            "TimeGenerated": time_generated,
            "Level": level,
            "Environment": self._environment,
            "ExceptionMessage": exception_message,
            "Message": message
        }]

        try:
            client.upload(rule_id=rule_id, stream_name=stream_name, logs=body)
        except Exception as e:
            logging.warning(f"Upload failed: {e}")

    @staticmethod
    def _execute_command(command_str: str) -> None:
        """
        Executes a bash command.
        :param command_str: bash command
        """
        command = Command(command_str)
        command.run(Path(os.getcwd()))
        if command.returncode != 0:
            raise Exception(f"Command {command_str} is not executed")


if __name__ == "__main__":
    hostname = socket.gethostname()
    if 'dt' in hostname:
        DbUpdatesReanalysis(environment='dt')
    if 'ap' in hostname:
        DbUpdatesReanalysis(environment='ap')
