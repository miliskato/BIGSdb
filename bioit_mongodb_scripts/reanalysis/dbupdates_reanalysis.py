import logging
import os
import socket
import time
from datetime import datetime, timedelta
from pathlib import Path

from bioit_mongodb_scripts.reanalysis.reanalysis_submitter_azure import _BatchPipelinesReanalysis
from bioit_mongodb_scripts.tempid_replacer_azure import _TempidReplacer
from bioit_mongodb_scripts.util.command.command import Command
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data
from bioit_mongodb_scripts.util_azure.connect_azure import ConnectAzure
from azure.monitor.ingestion import LogsIngestionClient

REMOVE_LOGS = 'find /var/log/dbupdate-logs/ -maxdepth 1 -mtime +28 -exec rm -rf {} \; 2>/dev/null'
DBUPDATES = 'export DB_UPD_ROOT="/opt/db_update"; export XDG_CACHE_HOME="/var/cache/dbupdate_cache"; /opt/db_update/dbupdate/scripts/bash/update_weekly.sh >> /var/log/dbupdate-logs/$(date +"%Y_%m_%d_%H-%M-%S")_updatelog.txt 2>&1'
DEALLOCATE_VM = 'az login --identity; az vm deallocate -n $(hostname) -g $(curl -s -H Metadata:true --noproxy "*" "http://169.254.169.254/metadata/instance?api-version=2021-02-01" | python3 -c \'import sys, json; print(json.load(sys.stdin)["compute"]["resourceGroupName"])\')'


class DbUpdatesReanalysis:
    """
    This class disables jobs in the batch account of the given environment, checks whether database updates can be
    carried out, executes the database updates, enables jobs again, launches the reanalysis and eventually
    deallocates the dbupdates VM.
    """

    def __init__(self, dtap: str) -> None:
        """
        Initialises the class, connects to the keyvault and batch account associated with the environment
        and executes the main functions.
        :param dtap: dev, test, acc, or prod
        :return: None
        """
        try:
            filename_log = f"/var/log/dbupdate-logs/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_log.txt"
            logging.basicConfig(filename=filename_log, filemode='w', level=logging.DEBUG,
                                format='%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
            self._dtap = dtap
            self._mongo_config_data = get_mongodb_config_data()
            self._connection_azure = ConnectAzure(self._dtap)
            self._batch_client = self._connection_azure.connect_to_batch_client()
            self._disable_jobs()
            self._execution_dbupdates()
            self._enable_jobs()
            self._execution_reanalysis()
        except Exception as e:
            self._enable_jobs()
            logging.error(f"An exception occurred during the database updates and the automated reanalysis: {e}")
            message_log = "An error occurred during the database updates and launching of the reanalysis"
            self._send_log_entry(level="Error", exception_message=str(e), message=message_log,
                                 stream_name="Custom-DbupdatesReanalysis_CL")
        finally:
            self._execute_command(DEALLOCATE_VM)

    def _execution_dbupdates(self) -> None:
        """
        Checks whether the database updates can be carried out, removes logs older than 4 weeks, executes the
        database updates and executes the tempid replacer.
        :return: None
        """
        self._check_dbupdates()
        self._execute_command(REMOVE_LOGS)
        self._execute_command(DBUPDATES)
        self._execution_tempid_replacer()

    def _check_dbupdates(self, max_hours: int = 10, sleep_minutes: int = 20) -> None:
        """
        Checks whether the database updates can be carried out (no tasks running). If not, it keeps regularly checking
        whether the database updates can be carried out. If the database updates can't be carried out after a maximum
        time, it will raise an exception.
        :param max_hours: How many hours it will maximally wait until raising an exception
        :param sleep_minutes: After how many minutes it will check again the status of the tasks
        """
        start_time = datetime.now()
        while datetime.now() - start_time < timedelta(hours=max_hours):
            self._get_task_status()
            if any(status == "running" for status in self._tasks_status):
                logging.info("Still tasks running, database updates can't be carried out")
                time.sleep(sleep_minutes * 60)
            else:
                logging.info("Database updates can be carried out")
                break  # Break out of the loop if no tasks are running
        else:
            raise Exception("Maximum waiting time has passed, database updates can't be carried out")

    def _execution_tempid_replacer(self) -> None:
        schemes = ['mlst', 'cgmlst', 'mlst_warwick', 'mlst_pasteur']
        for species in self._mongo_config_data['species']:
            for scheme in schemes:
                _TempidReplacer(scheme, species, self._dtap)

    def _execution_reanalysis(self) -> None:
        """
        Executes the reanalysis script.
        :return: None
        """
        for species in self._mongo_config_data['species']:
            _BatchPipelinesReanalysis(species, self._dtap)

    def _disable_jobs(self, retries: int = 3, timeout: int = 60 * 5, disable_tasks: str = "wait") -> None:
        """
        Disables all the jobs of a specific batch account.
        :param retries: Number of retries
        :param timeout: Waiting time until trying again
        :param disable_tasks: requeue, terminate or wait
        :return: None
        """
        for job in self._batch_client.job.list():
            job_disabled = False
            for retry in range(retries):
                try:
                    if job.state not in ('disabled', 'disabling'):
                        self._batch_client.job.disable(job.id, disable_tasks)
                        logging.info(f"Job {job.id} has been successfully disabled.")
                        job_disabled = True
                        break
                    else:
                        logging.info(f"Job {job.id} was already disabled.")
                        job_disabled = True
                        break
                except Exception as e:
                    message_log = f"Job {job.id} could not be disabled: {e}."
                    logging.info(message_log)
                    time.sleep(timeout)
            if not job_disabled:
                raise Exception(f"Job {job.id} could not be disabled")

    def _enable_jobs(self, retries: int = 3, timeout: int = 60 * 5) -> None:
        """
        Enables all the jobs of a specific batch account.
        :param retries: Number of retries
        :param timeout: Waiting time until trying again
        :return: None
        """
        for job in self._batch_client.job.list():
            job_enabled = False
            for retry in range(retries):
                try:
                    if job.state not in ('active', 'enabling'):
                        self._batch_client.job.enable(job.id)
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

    def _get_task_status(self) -> None:
        """
        Gets the status of all the tasks for all the jobs of a specific batch account.
        :return: None
        """
        tasks_status = []
        for job in self._batch_client.job.list():
            # Get the list of tasks for the current job
            tasks = self._batch_client.task.list(job.id)
            for task in tasks:
                task_status = task.state
                tasks_status.append(task_status)
        self._tasks_status = tasks_status

    def _send_log_entry(self, level: str, exception_message: str, message: str, stream_name: str):
        endpoint = self._connection_azure.keyvault_client.get_secret('DATA-COLLECTION-ENDPOINT-DBUPDATES')
        client = LogsIngestionClient(endpoint=endpoint, credential=self._connection_azure.credential)
        rule_id = self._connection_azure.keyvault_client.get_secret('DBUPDATES-REANALYSIS-RULE-ID')

        time_generated = datetime.now().isoformat()
        body = [{
            "TimeGenerated": time_generated,
            "Level": level,
            "Environment": self._dtap,
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
        Executes a bash command
        :param command_str: bash command
        """
        command = Command(command_str)
        command.run(Path(os.getcwd()))
        if command.returncode != 0:
            raise Exception(f"Command {command_str} is not executed")


if __name__ == "__main__":
    hostname = socket.gethostname()
    if 'dt' in hostname:
        DbUpdatesReanalysis(dtap='dev')
    else:
        print("Execution of dbupdates and launching of reanalysis not yet implemented on ap.")

