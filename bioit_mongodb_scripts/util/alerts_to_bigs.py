import datetime
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple, Union, Optional

import numpy as np

from bioit_bigsdb_scripts.components.psql import TblIsolates, TblAlerts, TblAlertDetails, TblAlertDetailsFieldOrder, \
    TblClassificationSchemes
from bioit_mongodb_scripts.util.python_utility_functions import get_bigsdb_config_data


class AlertsToBigs:
    """
    For the currently inserted new isolates, and new versions of isolates, evaluates whether they trigger
    warnings/alerts and inserts/updates these accordingly.
    """
    def __init__(self, list_of_new_isolates_inserted_in_bigsdb: List[Dict[str, Union[str, int]]],
                 list_of_new_versions_inserted_in_bigsdb: List[Dict[str, Union[str, int]]],
                 species: str, cgmlst_bigsdb_scheme_id: int, naive_clustering_distance_matrix_file: Path) -> None:
        """
        Initializes this class and executes the main function.
        :param list_of_new_isolates_inserted_in_bigsdb: List of dictionaries of relevant data concerning newly
        sql-inserted isolates.
        :param list_of_new_versions_inserted_in_bigsdb: List of dictionaries of relevant data concerning newly
        sql-inserted versions of existing isolates with different cgSTs than the previous version.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param cgmlst_bigsdb_scheme_id: The bigsdb SQL id of the cgMLST scheme
        :param naive_clustering_distance_matrix_file: path to the distance matrix file
        :return: None
        """
        self._list_of_new_isolates_inserted_in_bigsdb = list_of_new_isolates_inserted_in_bigsdb
        self._list_of_new_versions_inserted_in_bigsdb = list_of_new_versions_inserted_in_bigsdb
        self._species = species
        self._cgmlst_bigsdb_scheme_id = cgmlst_bigsdb_scheme_id
        self._naive_clustering_distance_matrix_file = naive_clustering_distance_matrix_file
        self._bigsdb_config_data = get_bigsdb_config_data()
        if not self._bigsdb_config_data['alerts'].get(self._species):
            return
        self._distance_matrix: np.array = \
            np.load(str(self._naive_clustering_distance_matrix_file))
        self._timeframe_is_infinite = self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] > 10000
        if not self._timeframe_is_infinite:
            self._timedelta_timeframe = datetime.timedelta(
                days=(self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] * 31))

        """
        Distance matrix evaluation
        """
        self._evaluate_warning_and_alert_for_investigation_method('distance matrix')

        """
        Single linkage evaluation
        """
        self._evaluate_warning_and_alert_for_investigation_method('single linkage')

    def _evaluate_warning_and_alert_for_investigation_method(self, investigation_method: str) -> None:
        """
        For the currently inserted new isolates, and new versions of isolates, evaluates whether they trigger
        warnings/alerts using the given investigation method and inserts/updates these accordingly.
        :param investigation_method: 'single linkage' or 'distance matrix'
        :return: None
        """
        if investigation_method not in ['distance matrix', 'single linkage']:
            raise ValueError("investigation method should be one of 'distance matrix' or 'single linkage'!")
        if investigation_method == 'single linkage':
            # Query the bigsdb classification scheme id's for both thresholds
            with TblClassificationSchemes(self._species, 'isolates') as isolates_clsch_psql_tbl:
                for threshold_key in ['threshold_alert', 'threshold_warning']:
                    self._bigsdb_config_data['alerts'][self._species][f'{threshold_key}_classification_scheme_id'] = \
                        isolates_clsch_psql_tbl.select_cgschemeid_by_threshold(
                            (self._bigsdb_config_data['alerts'][self._species][threshold_key],))[0][0]

        logging.info(f'Computing warnings/alerts from {investigation_method} for isolates just inserted into bigsdb')
        self.__evaluate_warning_and_alert_for_new_versions(investigation_method)
        self.__evaluate_warning_and_alert_for_new_isolates(investigation_method)
        
    def __evaluate_warning_and_alert_for_new_versions(self, investigation_method: str) -> None:
        """
        Part 1:
        Check whether new versions have different cgST's than their previous version and 
        whether any alerts/warnings are present for the previous version.
        :param investigation_method: distance matrix or single linkage
        :return: None
        """
        for new_version in self._list_of_new_versions_inserted_in_bigsdb:
            with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
                previous_alert_id_and_alert_type_in_bigs = isolates_alertsdet_psql_tbl.select_alert_for_isolate(
                    (new_version['isolate_name'], investigation_method))
            if len(previous_alert_id_and_alert_type_in_bigs) == 1:
                alert_id = previous_alert_id_and_alert_type_in_bigs[0][0]
                alert_type = previous_alert_id_and_alert_type_in_bigs[0][1]
                # Treat new version with different cgst as new isolate, except that it will have to update
                # instead of insert, add extra info (alert id and alert type) for it to be able to do that
                new_version['alert_id'] = alert_id
                new_version['previous_version_alert_type'] = alert_type
                self._list_of_new_isolates_inserted_in_bigsdb.append(new_version)
                # After this, part 2 is executed on these

    def __evaluate_warning_and_alert_for_new_isolates(self, investigation_method: str) -> None:
        """
        Part 2:
        Evaluate alerts for newly inserted isolates + newly inserted isolate versions where the cgST changed.
        :param investigation_method: distance matrix or single linkage
        :return: None
        """
        for isolate in self._list_of_new_isolates_inserted_in_bigsdb:
            if isolate['cgST'] is None:
                continue

            # order of keys below is important, if alert is triggered we'll break because warning will be redundant
            for threshold_key in ['threshold_alert', 'threshold_warning']:
                # get all cgSTs within distance, includes self
                distance_threshold = self._bigsdb_config_data['alerts'][self._species][threshold_key]
                similar_cgsts_from_matrix = self.___get_similar_cgsts_from_matrix(distance_threshold, isolate['cgST'])

                isolation_date = datetime.datetime.strptime(isolate['isolation_date'], '%d/%m/%Y')
                queried_isolates = self.___query_isolates_according_to_thresholds(similar_cgsts_from_matrix, isolate['cgST'],
                                                                                  isolation_date, investigation_method,
                                                                                  threshold_key)
                if len(queried_isolates) > 1:
                    subject_isolate_tuple = None
                    for isolate_tuple in queried_isolates:
                        if isolate_tuple[1] == isolate['isolate_name']:
                            subject_isolate_tuple = isolate_tuple
                            break
                    if subject_isolate_tuple is None:
                        exceptionmessage = f"While evaluating alerts, the tuple for the subject isolate " \
                                           f"{isolate['isolate_name']} was not found in the output of the sql query"
                        logging.error(exceptionmessage)
                        raise Exception(exceptionmessage)
                    # Assess whether number of cases threshold was surpassed
                    if len(queried_isolates) >= self._bigsdb_config_data['alerts'][self._species]['number_of_cases']:
                        if self._timeframe_is_infinite:
                            if not isolate.get('alert_id'):  # check if we're not dealing with reanalysis/resequencing
                                self.___insert_item_into_alerts(threshold_key.split('_')[-1],
                                                                investigation_method, subject_isolate_tuple,
                                                                similar_cgsts_from_matrix, distance_threshold)
                            else:
                                if threshold_key == 'threshold_alert' and \
                                        isolate.get('previous_version_alert_type') == 'warning':
                                    self.___update_warning_to_alert(str(isolate['alert_id']),
                                                                    str(distance_threshold))
                                self.___update_variable_details_for_alert(
                                    str(isolate['alert_id']), similar_cgsts_from_matrix,
                                    investigation_method,
                                    threshold_key.split('_')[-1],
                                    subject_clgr=queried_isolates[0][4] if investigation_method == 'single linkage' else None)
                                self.___update_identifiers_for_alert(str(isolate['alert_id']),
                                                                     str(subject_isolate_tuple[0]),
                                                                     isolate["isolate_name"])
                        else:  # not self._timeframe_is_infinite
                            """In this case we know that in **double** of the requested timeframe, the isolate number 
                             threshold is surpassed.
                            Therefore we need to evaluate all daily-sliding windows (with lengths equal to requested 
                             timeframe) here to check whether a sliding window surpasses the threshold. 
                            If multiple sliding windows surpass the threshold, and they do not have the same isolates
                             contents, then the contents need to be weighed to see which sliding window will be used.
                            The weight of isolates in a sliding window is equal to 1 divided by the number of days 
                             apart from the isolate under investigation. The sliding window with the highest sum of 
                             all weights then 'wins'. In case of an ex aequo, the sliding window closest to today will
                             be used. 
                            Likewise, if multiple sliding windows surpass the threshold, but they all 
                             contain the same isolates, then the sliding window closest to today will be used.
                            """
                            analysis_day = isolation_date.date()
                            sliding_windows_by_weight: List[Tuple[float, datetime.date, datetime.date]] = []
                            for window_start, window_end in zip(self.loop_over_days(analysis_day - self._timedelta_timeframe, analysis_day),
                                                                self.loop_over_days(analysis_day, analysis_day + self._timedelta_timeframe)):
                                isolates_count = 0
                                isolates_weight = 0
                                for queried_isolate in queried_isolates:
                                    if window_start <= queried_isolate[2] <= window_end:
                                        isolates_count += 1
                                        isolates_weight += 1 / (abs((analysis_day - queried_isolate[2]).days) if (analysis_day - queried_isolate[2]).days != 0 else 1)
                                    else:
                                        continue
                                if isolates_count >= self._bigsdb_config_data['alerts'][self._species]['number_of_cases']:
                                    sliding_windows_by_weight.append((isolates_weight, window_start, window_end))
                            if len(sliding_windows_by_weight) == 0:
                                # No sliding windows meeting the threshold were found
                                logging.info(f"no sliding windows meeting the threshold criteria were found for isolate {isolate['isolate_name']} for {threshold_key}")
                                continue
                            # sort the sliding windows so that the weights and dates are sorted in descending order
                            sliding_windows_by_weight.sort(reverse=True)
                            if not isolate.get('alert_id'):  # check if we're not dealing with reanalysis/resequencing
                                self.___insert_item_into_alerts(threshold_key.split('_')[-1],
                                                                investigation_method, subject_isolate_tuple,
                                                                similar_cgsts_from_matrix, distance_threshold,
                                                                sliding_windows_by_weight[0][1].strftime('%Y-%m-%d'),
                                                                sliding_windows_by_weight[0][2].strftime('%Y-%m-%d'))
                            else:
                                if threshold_key == 'threshold_alert' and \
                                        isolate.get('previous_version_alert_type') == 'warning':
                                    self.___update_warning_to_alert(str(isolate['alert_id']),
                                                                    str(distance_threshold))
                                self.___update_variable_details_for_alert(
                                    str(isolate['alert_id']), similar_cgsts_from_matrix,
                                    investigation_method,
                                    threshold_key.split('_')[-1],
                                    sliding_windows_by_weight[0][1].strftime('%Y-%m-%d'),
                                    sliding_windows_by_weight[0][2].strftime('%Y-%m-%d'),
                                    subject_clgr=queried_isolates[0][4] if investigation_method == 'single linkage' else None)
                                self.___update_identifiers_for_alert(str(isolate['alert_id']),
                                                                     str(subject_isolate_tuple[0]),
                                                                     isolate["isolate_name"])
                        if threshold_key == 'threshold_alert':
                            # if Alert is triggered, break the for loop because a warning would be redundant
                            if investigation_method == 'single linkage':
                                with TblIsolates(self._species) as isolates_psql_tbl:
                                    queried_isolates = isolates_psql_tbl.select_isolates_by_cluster_group(
                                        (self._bigsdb_config_data['alerts'][self._species][
                                             f'threshold_warning_classification_scheme_id'],
                                         self._cgmlst_bigsdb_scheme_id, isolate['cgST']))
                            break

    def ___get_similar_cgsts_from_matrix(self, distance_threshold: int, isolate_cgst: int) -> List[str]:
        """
        Returns cgsts with <= dist_threshold diff with current isolate cgst based on the distance matrix
        :param distance_threshold: distance threshold from config file
        :param isolate_cgst: cgst of the current isolate
        :return: list of similar cgsts
        """
        row_cgst = self._distance_matrix[isolate_cgst - 1]
        indices_for_similar_cgsts = np.where(row_cgst <= distance_threshold)[0]
        return [str(x + 1) for x in indices_for_similar_cgsts]

    def ___query_isolates_according_to_thresholds(self, cgsts_as_list_of_str: list[str], cgst_of_current_isolate: int, isolation_date: datetime.datetime,
                                                  investigation_method: str, threshold_key: str) -> List[Optional[Tuple[Any]]]:
        """
        Queries isolates according to the given input parameters.
        :param cgsts_as_list_of_str: cgSTs belonging within given threshold key's threshold
        :param cgst_of_current_isolate: cgST of the current isolate
        :param isolation_date: isolation date of the current isolate
        :param investigation_method: 'distance matrix' or 'single linkage'
        :param threshold_key: 'threshold_alert' or 'threshold_warning'
        :return: List of tuples of queried isolates
        """
        if investigation_method == 'distance matrix':
            queried_isolates = self.____get_queried_isolates_with_distance_matrix(cgsts_as_list_of_str, isolation_date)
        else:
            queried_isolates = self.____get_queried_isolates_with_single_linkage(cgst_of_current_isolate, isolation_date, threshold_key)
        return queried_isolates

    def ____get_queried_isolates_with_distance_matrix(self, cgsts_as_list_of_str: list[str, ...], isolation_date: datetime.datetime) -> List[Optional[Tuple[Any]]]:
        """
        Return isolates belonging to the alert according to the matrix method
        :param cgsts_as_list_of_str: List containing similar cgsts from the distance matrix based on a specific threshold
        :param isolation_date: isolation date of the isolate under evaluation for alerts
        :return: List of tuples of queried isolates
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            if self._timeframe_is_infinite:
                queried_isolates = isolates_psql_tbl.select_isolates_by_cgsts(
                    (self._cgmlst_bigsdb_scheme_id, cgsts_as_list_of_str))
            else:
                start_date = (isolation_date - self._timedelta_timeframe).strftime('%Y-%m-%d')
                end_date = (isolation_date + self._timedelta_timeframe).strftime('%Y-%m-%d')
                queried_isolates = isolates_psql_tbl.select_isolates_by_cgsts_and_between_dates(
                    (self._cgmlst_bigsdb_scheme_id, cgsts_as_list_of_str, start_date, end_date))
        return queried_isolates

    def ____get_queried_isolates_with_single_linkage(self, cgst_of_current_isolate: int, isolation_date: datetime.datetime, threshold_key: str) -> List[Optional[Tuple[Any]]]:
        """
        Return isolates belonging to the alert according to the single linkage method
        :param cgst_of_current_isolate: cgST of the current isolate
        :param isolation_date: isolation date of the isolate under evaluation for alerts
        :param threshold_key: 'threshold_alert' or 'threshold_warning'
        :return: List of tuples of queried isolates
        """
        with TblIsolates(self._species) as isolates_psql_tbl:
            if self._timeframe_is_infinite:
                queried_isolates = isolates_psql_tbl.select_isolates_by_cluster_group(
                    (self._bigsdb_config_data['alerts'][self._species][
                         f'{threshold_key}_classification_scheme_id'],
                     self._cgmlst_bigsdb_scheme_id, str(cgst_of_current_isolate)))
            else:
                start_date = (isolation_date - self._timedelta_timeframe).strftime('%Y-%m-%d')
                end_date = (isolation_date + self._timedelta_timeframe).strftime('%Y-%m-%d')
                queried_isolates: list[Optional[tuple[Any]]] = isolates_psql_tbl. \
                    select_isolates_by_cluster_group_and_between_dates(
                    (self._bigsdb_config_data['alerts'][self._species][
                         f'{threshold_key}_classification_scheme_id'],
                     self._cgmlst_bigsdb_scheme_id, str(cgst_of_current_isolate), start_date, end_date))
        return queried_isolates

    def ___update_identifiers_for_alert(self, alert_id: str, new_isolate_bigsdb_id: str, isolate_name: str) -> None:
        """
        Updates id related fields for a given alert.
        :param alert_id: id of the alert cast as str
        :param new_isolate_bigsdb_id: id of the new isolate version cast as str
        :param isolate_name: the name of the isolate
        :return: None
        """
        # update identifier data
        with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
            isolates_alertsdet_psql_tbl.update_details_for_alert_id((
                f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?page=info&db=bigsdb_{self._species}_isolates&id='
                f'{new_isolate_bigsdb_id}" target="_blank">{isolate_name}</a></p>',
                'trigger', alert_id))
            isolates_alertsdet_psql_tbl.update_details_for_alert_id((new_isolate_bigsdb_id,
                                                                     'isolate_id', alert_id))

    def ___insert_item_into_alerts(self, alert_type: str, investigation_method: str, subject_isolate_tuple: Tuple[Any],
                                   cgsts: List[str], threshold: int, start_date: str = None,
                                   end_date: str = None) -> None:
        """
        Inserts a new alert/warning (=type) into the alerts table, and its details in the alert_details table
        :param alert_type: warning/alert
        :param investigation_method: distance matrix or single linkage
        :param subject_isolate_tuple: subject isolate tuple containing bigsdb isolate id, isolate name, isolation date,
        and the cgst of the subject
        :param cgsts: involved cgsts for this particular subject
        :param threshold: threshold; pathogen-specific threshold associated with the alert/warning
        :param start_date: str in YYYY-MM-DD format, pathogen specific timeframe start date
        :param end_date: str in YYYY-MM-DD format, pathogen specific timeframe end date
        :return: None
        """
        # unpack psql output tuple
        subject_isolate_id = subject_isolate_tuple[0]
        subject_isolate_name = subject_isolate_tuple[1]
        subject_isolation_date = subject_isolate_tuple[2]
        subject_cgst = subject_isolate_tuple[3]
        if investigation_method == 'single linkage':
            subject_clgr = subject_isolate_tuple[4]

        # insert into alerts table
        with TblAlerts(self._species) as isolates_alerts_psql_tbl:
            isolates_alerts_psql_tbl.insert_alert((alert_type, investigation_method))

        # insert into alert_details and alert_details_field_order tables
        with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl, \
                TblAlertDetailsFieldOrder(self._species) as isolates_alertsdetfo_psql_tbl:

            # insert trigger subject with href
            isolates_alertsdet_psql_tbl.insert_alert_metadata(
                ('trigger',
                 f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?page=info&db=bigsdb_{self._species}_isolates&id='
                 f'{subject_isolate_id}" target="_blank">{subject_isolate_name}</a></p>'))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger', 1))

            # insert trigger subject isolation date
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('trigger isolation date', subject_isolation_date))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger isolationdate', 2))

            # insert trigger subject cgst with href
            isolates_alertsdet_psql_tbl.insert_alert_metadata(
                ('trigger cgst',
                 f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?page=query&submit=1&db=bigsdb_{self._species}'
                 f'_isolates&designation_value1={subject_cgst}&designation_field1=s_{self._cgmlst_bigsdb_scheme_id}'
                 f'_cgST" target="_blank">{subject_cgst}</a></p>'))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger cgst', 3))

            if investigation_method == 'distance matrix':
                # insert all trigger subjects with javascript href
                cgsts_plaintext = '","'.join(cgsts)
                if self._timeframe_is_infinite:
                    url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
                else:
                    url = f'generateUrlCgstDate("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ' \
                          f'["{cgsts_plaintext}"], "{start_date}", "{end_date}")'
            else:  # investigation_method == 'single linkage':
                clgr_bigsdb_scheme_id = self._get_clgr_bigsdb_scheme_id(alert_type)
                if self._timeframe_is_infinite:
                    url = f'generateUrlClgr("{self._species}", "{clgr_bigsdb_scheme_id}", "{subject_clgr}")'
                else:
                    url = f'generateUrlClgrDate("{self._species}", "{clgr_bigsdb_scheme_id}", ' \
                          f'"{subject_clgr}", "{start_date}", "{end_date}")'

            html_element = f'<div id="trigger_subjects"><script type="text/javascript">replaceQueriedValue({url}, ' \
                           f'"trigger_subjects")</script>'
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('trigger subjects', html_element))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger subjects', 4))

            if investigation_method == 'distance matrix':
                # insert all isolates with query cgsts, independent of timeframe
                cgsts_as_str = ','.join(cgsts)
                url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
                isolates_alertsdet_psql_tbl.insert_alert_metadata(
                    ('cgsts time independent',
                     f'<div id="{cgsts_as_str}"><script type="text/javascript">addUrlToField({url}, '
                     f'"{cgsts_as_str}")</script>'))
                isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('cgsts time independent', 5))
            else:  # investigation_method == 'single linkage':
                clgr_bigsdb_scheme_id = self._get_clgr_bigsdb_scheme_id(alert_type)
                url = f'generateUrlClgr("{self._species}", "{clgr_bigsdb_scheme_id}", "{subject_clgr}")'
                isolates_alertsdet_psql_tbl.insert_alert_metadata(
                    ('cluster group',
                     f'<div id="{subject_clgr}"><script type="text/javascript">addUrlToField({url}, '
                     f'"{subject_clgr}")</script>'))
                isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('cluster group', 5))

            # insert threshold for information
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('cgmlst threshold', str(threshold)))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('cgmlst threshold', 6))

            # insert threshold for information
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('method', investigation_method))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('method', 7))

            # insert isolate id for backend information;
            # don't add it to the field order, and it will not be shown in the gui
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('isolate_id', subject_isolate_id))

    def ___update_variable_details_for_alert(self, alert_id: str, cgsts: List[str], investigation_method: str,
                                             alert_type: str, start_date: str = None, end_date: str = None,
                                             subject_clgr: str = None) -> None:
        """
        Updates an alerts' details in the alert_details table.
        :param alert_id: the id of the to be updated alert
        :param cgsts: involved cgsts for this particular subject
        :param investigation_method: distance matrix or single linkage
        :param alert_type: warning/alert
        :param start_date: str in YYYY-MM-DD format, pathogen specific timeframe start date
        :param end_date: str in YYYY-MM-DD format, pathogen specific timeframe end date
        :param subject_clgr: the subject's cluster group cast as str, only available when the investigation_method is single linkage
        :return: None
        """
        with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
            # update all trigger subjects with javascript href
            cgsts_plaintext = '","'.join(cgsts)

            if investigation_method == 'distance matrix':
                # insert all isolates with query cgsts, independent of timeframe
                cgsts_as_str = ','.join(cgsts)
                url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
                isolates_alertsdet_psql_tbl.update_details_for_alert_id(
                    (f'<div id="{cgsts_as_str}"><script type="text/javascript">addUrlToField({url}, '
                     f'"{cgsts_as_str}")</script>',
                     alert_id, 'cgsts time independent'))

                if self._timeframe_is_infinite:
                    url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
                else:
                    url = f'generateUrlCgstDate("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ' \
                          f'["{cgsts_plaintext}"], "{start_date}", "{end_date}")'
            else:  # investigation_method == 'single linkage':
                clgr_bigsdb_scheme_id = self._get_clgr_bigsdb_scheme_id(alert_type)
                if self._timeframe_is_infinite:
                    url = f'generateUrlClgr("{self._species}", "{clgr_bigsdb_scheme_id}", "{subject_clgr}")'
                else:
                    url = f'generateUrlClgrDate("{self._species}", "{clgr_bigsdb_scheme_id}", ' \
                          f'"{subject_clgr}", "{start_date}", "{end_date}")'
                isolates_alertsdet_psql_tbl.update_details_for_alert_id(
                    (f'<div id="{subject_clgr}"><script type="text/javascript">addUrlToField({url}, '
                     f'"{subject_clgr}")</script>',
                     alert_id, 'cluster group'))
            html_element = f'<div id="trigger_subjects"><script type="text/javascript">replaceQueriedValue({url}, ' \
                           f'"trigger_subjects")</script>'
            isolates_alertsdet_psql_tbl.update_details_for_alert_id((html_element, alert_id, 'trigger subjects'))

    def ___update_warning_to_alert(self, alert_id: str, distance_threshold: str) -> None:
        """
        Updates a warning to an alert, sets the status to pending regardless of previous status,
        and also updates the threshold.
        :param alert_id: alert_id cast as str
        :param distance_threshold: distance threshold cast as str
        :return: None
        """
        with TblAlerts(self._species) as isolates_alerts_psql_tbl, \
                TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
            isolates_alerts_psql_tbl.update_warning_to_alert_and_status_to_pending((alert_id,))
            isolates_alertsdet_psql_tbl.update_details_for_alert_id(
                (distance_threshold, alert_id, 'cgmlst threshold'))

    def _get_clgr_bigsdb_scheme_id(self, alert_type: str) -> str:
        """
        Function to get the scheme id for the classification/cluster group scheme corresponding to the
        alert/warning threshold.
        :param alert_type: warning/alert
        :return: a scheme id for the classification/cluster group scheme corresponding to the alert/warning threshold
        """
        return self._bigsdb_config_data['alerts'][self._species][f'threshold_{alert_type}_classification_scheme_id']

    @staticmethod
    def loop_over_days(start_date: datetime.date, end_date: datetime.date) -> Iterator[datetime.date]:
        """
        Loops over all days between two datetime.date 's and returns them one by one.
        :param start_date: loop start date
        :param end_date: loop end date
        :return: iterator over dates
        """
        current_date = start_date
        while current_date <= end_date:
            yield current_date
            current_date += datetime.timedelta(days=1)
