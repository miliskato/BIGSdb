from typing import Union

from bioit_bigsdb_scripts.components.psql import TblAlerts, TblAlertDetails, TblIsolates, TblAlertDetailsFieldOrder


class HostAlertsToBigs:
    """
    For the currently inserted new isolates, and new versions of isolates, evaluates whether they trigger an alert
    based on the hosts of the reference sequence and inserts/updates these accordingly.
    """

    def __init__(self, species: str, list_of_new_isolates_for_alerts: list[dict[str, Union[str, int]]],
                 list_of_new_versions_for_alerts: list[dict[str, Union[str, int]]]) -> None:
        """
        Initializes this class.
        :param species: Species
        :param list_of_new_isolates_for_alerts: List of dictionaries containing relevant data of newly
        sql-inserted isolates
        :param list_of_new_versions_for_alerts: List of dictionaries containing relevant data of newly
        sql-inserted isolate versions
        :return: None
        """
        self._species = species
        self._list_of_new_isolates_for_alerts = list_of_new_isolates_for_alerts
        self._list_of_new_versions_for_alerts = list_of_new_versions_for_alerts

    def evaluate_alerts_for_hosts(self) -> None:
        """
        Evaluates alerts based on the hosts of the reference sequence for newly inserted isolates / isolate versions.
        :return: None
        """
        self._evaluate_alerts_for_hosts_new_isolates()
        self._evaluate_alerts_for_hosts_new_versions()

    def _evaluate_alerts_for_hosts_new_isolates(self) -> None:
        """
        Evaluates alerts based on the hosts of the reference sequence for newly inserted isolates.
        :return: None
        """
        for isolate in self._list_of_new_isolates_for_alerts:
                self._insert_alert(isolate)

    def _evaluate_alerts_for_hosts_new_versions(self) -> None:
        """
        Evaluates alerts based on the hosts of the reference sequence for newly inserted isolate versions.
        :return: None
        """
        for isolate in self._list_of_new_versions_for_alerts:
            if not isolate['non_human_hosts']:
                self._delete_alert(isolate)
            else:
                self._update_alert(isolate)

    def _insert_alert(self, isolate: dict[str, str]) -> None:
        """
        Inserts an alert into the alerts and alert details tables.
        :param isolate: Dictionary of relevant data concerning newly sql-inserted isolates
        :return: None
        """
        isolate_name = isolate['isolate_name']
        non_human_hosts = isolate['non_human_hosts']
        isolate_id = self.__get_isolate_id(isolate_name, self._species)
        with TblAlerts(self._species) as alerts_psql_tbl:
            alerts_psql_tbl.insert_alert(('alert', 'hosts of reference sequence'))

        with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
            isolates_alertsdet_psql_tbl.insert_alert_metadata(
                ('trigger', f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?page=info&db=bigsdb_{self._species}_isolates&id='f'{isolate_id}" target="_blank">{isolate_name}</a></p>'))
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('non-human hosts', ", ".join(sorted(non_human_hosts))))
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('isolation date', isolate['isolation_date']))
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('method', 'hosts of reference sequence'))
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('isolate_id', isolate_id))

        with TblAlertDetailsFieldOrder(self._species) as isolates_alertsdetfo_psql_tbl:
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger', 1))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('non human hosts', 2))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('isolation date', 3))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('method', 4))

    def _update_alert(self, isolate: dict[str, str]) -> None:
        """
        Updates an already existing alert.
        :param isolate: Dictionary of relevant data concerning newly sql-inserted isolate versions
        :return: None
        """
        non_human_hosts = isolate['non_human_hosts']
        with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
            alert_id_and_alert_type = isolates_alertsdet_psql_tbl.select_alert_id_and_alert_type_for_isolate(
                (isolate['isolate_name'], 'hosts of reference sequence'))
            alert_id = alert_id_and_alert_type[0][0]
            alert_type = alert_id_and_alert_type[0][1]
            isolates_alertsdet_psql_tbl.update_details_for_alert_id((", ".join(sorted(non_human_hosts)), alert_id, alert_type))

        with TblAlerts(self._species) as alerts_psql_tbl:
            alerts_psql_tbl.update_status_to_pending((alert_id,))

    def _delete_alert(self, isolate: dict[str, str]) -> None:
        """
        Deletes an alert.
        :param isolate: Dictionary of relevant data concerning newly sql-inserted isolate versions
        :return: None
        """
        isolate_id = self.__get_isolate_id(isolate['isolate_name'], self._species)
        with TblAlerts(self._species) as alerts_psql_tbl:
            alerts_psql_tbl.delete_alert((isolate_id,))

    @staticmethod
    def __get_isolate_id(isolate_name: str, species: str) -> str:
        """
        Returns the isolate id for a given isolate name and species.
        :param isolate_name: Isolate name
        :param species: Species
        :return: Isolate id as string
        """
        with TblIsolates(species) as isolates_psql_tbl:
            isolate_id = isolates_psql_tbl.select_id_for_isolate((isolate_name,))
        return isolate_id
