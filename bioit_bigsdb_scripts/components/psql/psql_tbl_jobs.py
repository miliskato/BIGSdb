from typing import List, Optional, Tuple

from .databaseconnection import DatabaseConnection
from .psql_queries import PsqlQueries


class TblJobs(DatabaseConnection):
    """
    Bigs db jobs table
    """

    def __init__(self) -> None:
        """
        Initialises this class by opening a database connection.
        """
        super().__init__(None, 'jobs')

    def select_pid_of_started_jobs(self) -> List[Optional[Tuple[int]]]:
        """
        Select and return pid for jobs with status "started"
        :return: list of tuples of ints if "started" jobs are found
        """
        return self.execute(PsqlQueries.JOB_SEL_PID_STARTED_JOBS_TB_JOBS)

    def assigned_failed_status(self, param: Tuple[int]) -> None:
        """
        Set job status with these PIDs to "cancelled"
        :param param: variables to feed to the PSQL query, in this case, pid of jobs which are not running anymore
        :return: None
        """
        self.execute_query(PsqlQueries.JOBS_SET_FAILED_STATUS, param)
