import socket
import psutil
import sys
from pathlib import Path

PYTHONPATH = Path(__file__).resolve().parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_bigsdb_scripts.components.python_utility_functions import send_email
from bioit_bigsdb_scripts.components.psql import TblJobs

with TblJobs() as jobs_jobs_psql_tbl:

    try:
        list_pid = jobs_jobs_psql_tbl.select_pid_of_started_jobs()
        for job_tuple in list_pid:
            pid = job_tuple[0]
            module = job_tuple[1]
            stage = job_tuple[2]
            if not (psutil.pid_exists(pid)):
                jobs_jobs_psql_tbl.assigned_failed_status((pid,))
                send_email(f"💥 Job with PID {pid} was turn to failed status (it was executing stage '{stage}' of '{module}')",
                           subject=f"BISdb jobs killed on host {socket.gethostname()}")
    except Exception as e:
        print(e)