import datetime
import logging
from typing import Any, Dict, Iterator, List, Tuple, Union

import numpy as np

from bioit_bigsdb_scripts.components.psql import TblIsolates, TblAlerts, TblAlertDetails, TblAlertDetailsFieldOrder, \
    TblClassificationSchemes
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data


class AlertsToBigs:
    """
    For the currently inserted new isolates, and new versions of isolates, evaluates whether they trigger
    warnings/alerts and inserts/updates these accordingly.
    """
    def __init__(self, list_of_new_isolates_inserted_in_bigsdb: List[Dict[str, Union[str, int]]],
                 list_of_new_versions_inserted_in_bigsdb: List[Dict[str, Union[str, int]]],
                 species: str, cgmlst_bigsdb_scheme_id: int) -> None:
        """
        Initializes this class and executes the main function.
        :param list_of_new_isolates_inserted_in_bigsdb: List of dictionaries of relevant data concerning newly
        sql-inserted isolates.
        :param list_of_new_versions_inserted_in_bigsdb: List of dictionaries of relevant data concerning newly
        sql-inserted versions of existing isolates.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param cgmlst_bigsdb_scheme_id: The bigsdb SQL id of the cgMLST scheme
        :return: None
        """
        self._list_of_new_isolates_inserted_in_bigsdb = list_of_new_isolates_inserted_in_bigsdb
        self._list_of_new_versions_inserted_in_bigsdb = list_of_new_versions_inserted_in_bigsdb
        self._species = species
        self._cgmlst_bigsdb_scheme_id = cgmlst_bigsdb_scheme_id
        self._bigsdb_config_data = get_bigsdb_config_data()
        if not self._bigsdb_config_data['alerts'].get(self._species):
            return
        self._distance_matrix: np.array = \
            np.load(str(self._bigsdb_config_data['naive_clustering_distance_matrix_file']).
                    replace('species', self._species))
        self._timeframe_is_infinite = self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] > 10000

        """
        Distance matrix evaluation
        """
        self._cgst_isolatecount_dict: Dict[int, int] = {}
        self._cgst_date_isolatecount_dict: Dict[tuple[int, str], int] = {}

        # Initialize sets to keep track of affected isolates (to reevaluate because of retroapplicability)
        # and subject isolates (to substract from the affected isolates in order to not reevaluate)
        self._affected_isolates_tuples: set[Tuple[Any], ...] = set()
        self._subject_isolates_tuples: set[Tuple[Any], ...] = set()

        self._evaluate_warning_and_alert_from_distance_matrix()

        """
        Single linkage evaluation
        """
        self._clgr_isolatecount_dict: Dict[int, int] = {}
        self._clgr_date_isolatecount_dict: Dict[tuple[int, str], int] = {}

        self._affected_isolates_tuples: set[Tuple[Any], ...] = set()
        self._subject_isolates_tuples: set[Tuple[Any], ...] = set()

        self._evaluate_warning_and_alert_from_hierarchical_clustering()

    def _evaluate_warning_and_alert_from_distance_matrix(self) -> None:
        """
        For the currently inserted new isolates, and new versions of isolates, evaluates whether they trigger
        warnings/alerts and inserts/updates these accordingly.
        After the currently inserted isolates are evaluated, also evaluates possibly affected isolates,
        and inserts/updates their warnings/alerts accordingly.
        :return: None
        """
        investigation_method = 'distance matrix'
        logging.info('Computing warnings/alerts from distance matrix for isolates just inserted into bigsdb')
        self.__evaluate_warning_and_alert_for_new_versions(investigation_method)
        self.__evaluate_warning_and_alert_for_new_isolates(investigation_method)

        logging.info('Computing warnings/alerts from distance matrix for isolates already in bigsdb, '
                     'but affected by isolates just inserted into bigsdb')
        # Remove subject isolate tuples from affected ones in order to not reevaluate them
        self._affected_isolates_tuples.difference_update(self._subject_isolates_tuples)
        self.__evaluate_warning_and_alert_for_affected_isolates(investigation_method)

    def _evaluate_warning_and_alert_from_hierarchical_clustering(self) -> None:
        """
        For the currently inserted new isolates, and new versions of isolates, evaluates whether they trigger
        warnings/alerts and inserts/updates these accordingly.
        After the currently inserted isolates are evaluated, also evaluates possibly affected isolates,
        and inserts/updates their warnings/alerts accordingly.
        :return: None
        """
        investigation_method = 'single linkage'

        # Query the bigsdb classification scheme id's for both thresholds
        with TblClassificationSchemes(self._species, 'isolates') as isolates_clsch_psql_tbl:
            for threshold_key in ['threshold_alert', 'threshold_warning']:
                self._bigsdb_config_data['alerts'][self._species][f'{threshold_key}_classification_scheme_id'] = \
                    isolates_clsch_psql_tbl.select_cgschemeid_by_threshold(
                        (self._bigsdb_config_data['alerts'][self._species][threshold_key],))[0][0]

        logging.info('Computing warnings/alerts from single linkage clustering for isolates just inserted into bigsdb')
        self.__evaluate_warning_and_alert_for_new_versions(investigation_method)
        self.__evaluate_warning_and_alert_for_new_isolates(investigation_method)

        logging.info('Computing warnings/alerts from single linkage clustering for isolates already in bigsdb, '
                     'but affected by isolates just inserted into bigsdb')
        # Remove subject isolate tuples from affected ones in order to not reevaluate them
        print(self._affected_isolates_tuples)
        print(self._subject_isolates_tuples)
        self._affected_isolates_tuples.difference_update(self._subject_isolates_tuples)
        self.__evaluate_warning_and_alert_for_affected_isolates(investigation_method)
        
    def __evaluate_warning_and_alert_for_new_versions(self, investigation_method) -> None:
        """
        Part 1:
        Check whether new versions have different cgST's than their previous version and 
        whether any alerts/warnings are present for the previous version.
        :param investigation_method: distance matrix or single linkage
        :return: None
        """
        for new_version in self._list_of_new_versions_inserted_in_bigsdb:
            with TblIsolates(self._species) as self._isolates_psql_tbl:
                cgsts_tuples = self._isolates_psql_tbl.select_cgsts_of_two_latest_versions_of_isolate(
                    (self._cgmlst_bigsdb_scheme_id, self._cgmlst_bigsdb_scheme_id, new_version['isolate_name']))
            previous_version_bigsdb_id = cgsts_tuples[1][0]
            with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
                previous_version_warning_or_alert_info = isolates_alertsdet_psql_tbl.select_alert_for_isolate(
                    (str(previous_version_bigsdb_id), investigation_method))
            alert_id = None
            alert_type = None
            if len(previous_version_warning_or_alert_info) == 1:
                alert_id = previous_version_warning_or_alert_info[0][0]
                alert_type = previous_version_warning_or_alert_info[0][1]
            # check if cgsts changed between current new version and previous version
            if cgsts_tuples[0][1] == cgsts_tuples[1][1]:
                # if it didn't update any alert
                new_version_bigsdb_id = cgsts_tuples[0][0]
                if len(previous_version_warning_or_alert_info) == 1:
                    # update id related fields
                    self.___update_identifiers_for_alert(str(alert_id),
                                                         str(new_version_bigsdb_id),
                                                         new_version["isolate_name"])
                # do not add to subject isolates here, because we're not actually evaluating if anything is triggered,
                # therefore later, this isolate could be added to the affected isolates and reevaluated if needed.
            else:
                # Treat new version with different cgst as new isolate, except that it will have to update
                # instead of insert, add extra info for it to be able to do that
                new_version['alert_id'] = alert_id
                new_version['previous_version_alert_type'] = alert_type
                self._list_of_new_isolates_inserted_in_bigsdb.append(new_version)
                # After this, part 2 is executed on these

    def __evaluate_warning_and_alert_for_new_isolates(self, investigation_method) -> None:
        """
        Part 2:
        Evaluate alerts for newly inserted isolates + newly inserted isolate versions where the cgST changed.
        :param investigation_method: distance matrix or single linkage
        :return: None
        """
        for isolate in self._list_of_new_isolates_inserted_in_bigsdb:
            if isolate['cgST'] is None:
                continue
            # extract row from distance matrix
            row_cgst = self._distance_matrix[isolate['cgST'] - 1]
            # order of keys below is important, if alert is triggered we'll break because warning will be redundant
            for threshold_key in ['threshold_alert', 'threshold_warning']:
                distance_threshold = self._bigsdb_config_data['alerts'][self._species][threshold_key]
                # get all cgSTs within distance, includes self
                indices = np.where(row_cgst <= distance_threshold)[0]
                cgsts = [x + 1 for x in indices]
                cgsts_as_tuple_of_str = tuple(str(x + 1) for x in indices)

                with TblIsolates(self._species) as self._isolates_psql_tbl:
                    if self._timeframe_is_infinite:
                        if investigation_method == 'distance matrix':
                            queried_isolates = self._isolates_psql_tbl.select_isolates_by_cgsts(
                                (self._cgmlst_bigsdb_scheme_id, cgsts_as_tuple_of_str))
                            self._cgst_isolatecount_dict[isolate['cgST']] = len(queried_isolates)
                        elif investigation_method == 'single linkage':
                            queried_isolates = self._isolates_psql_tbl.select_isolates_by_cluster_group(
                                (self._bigsdb_config_data['alerts'][self._species][
                                     f'{threshold_key}_classification_scheme_id'],
                                 self._cgmlst_bigsdb_scheme_id, isolate['cgST']))
                            # all cluster groups are the same in the query; take 4th element (cluster group) of first
                            # tuple, which always has to exist because the isolate itself is definitely queried)
                            self._clgr_isolatecount_dict[queried_isolates[0][4]] = len(queried_isolates)
                    else:
                        analysis_date = datetime.datetime.strptime(isolate['isolation_date'], '%d/%m/%Y - %X')
                        timedelta_timeframe = datetime.timedelta(days=(
                                self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] * 31))
                        start_date = (analysis_date - timedelta_timeframe).strftime('%Y-%m-%d')
                        end_date = (analysis_date + timedelta_timeframe).strftime('%Y-%m-%d')
                        if investigation_method == 'distance matrix':
                            queried_isolates = self._isolates_psql_tbl.select_isolates_by_cgsts_and_between_dates(
                                (self._cgmlst_bigsdb_scheme_id, cgsts_as_tuple_of_str, start_date, end_date))
                            self._cgst_date_isolatecount_dict[(isolate['cgST'], analysis_date.strftime('%Y-%m-%d'))] = \
                                len(queried_isolates)
                        elif investigation_method == 'single linkage':
                            queried_isolates = self._isolates_psql_tbl.\
                                select_isolates_by_cluster_group_and_between_dates(
                                    (self._bigsdb_config_data['alerts'][self._species][
                                         f'{threshold_key}_classification_scheme_id'],
                                     self._cgmlst_bigsdb_scheme_id, isolate['cgST'], start_date, end_date))
                            self._clgr_date_isolatecount_dict[(queried_isolates[0][4], analysis_date.strftime('%Y-%m-%d'))] = \
                                len(queried_isolates)
                    if len(queried_isolates) > 1:
                        subject_isolate_tuple = None
                        for isolate_tuple in queried_isolates:
                            self._affected_isolates_tuples.add(isolate_tuple)
                            # add subject isolates to set of tuples so that they can
                            # easily be substracted from the affected isolates later.
                            if isolate_tuple[1] == isolate['isolate_name']:
                                subject_isolate_tuple = isolate_tuple
                                self._subject_isolates_tuples.add(subject_isolate_tuple)
                        if subject_isolate_tuple is None:
                            exceptionmessage = f"While evaluating alerts, the tuple for the subject isolate " \
                                               f"{isolate['isolate_name']} was not found in the output of the sql query"
                            logging.error(exceptionmessage)
                            raise Exception(exceptionmessage)
                        # Assess whether number of cases threshold was surpassed
                        if len(queried_isolates) >= \
                                self._bigsdb_config_data['alerts'][self._species]['number_of_cases']:
                            if self._timeframe_is_infinite:
                                if not isolate.get('alert_id'):  # check if we're not dealing with reanalysis/resequencing
                                    self.___insert_item_into_alerts(threshold_key.split('_')[-1],
                                                                    investigation_method, subject_isolate_tuple,
                                                                    cgsts, distance_threshold)
                                else:
                                    if threshold_key == 'threshold_alert' and \
                                            isolate.get('previous_version_alert_type') == 'warning':
                                        self.___update_warning_to_alert(str(isolate['alert_id']),
                                                                        str(distance_threshold))
                                    self.___update_variable_details_for_alert(
                                        str(isolate['alert_id']), cgsts,
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
                                analysis_day = analysis_date.date()
                                sliding_windows_by_weight: List[Tuple[float, datetime.date, datetime.date]] = []
                                for window_start, window_end in zip(self.loop_over_days(analysis_day - timedelta_timeframe, analysis_day),
                                                                    self.loop_over_days(analysis_day, analysis_day + timedelta_timeframe)):
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
                                    logging.info(f"no sliding windows meeting the threshold criteria were found for isolate {isolate['isolate_name']}")
                                    continue
                                # sort the sliding windows so that the weights and dates are sorted in descending order
                                sliding_windows_by_weight.sort(reverse=True)
                                if not isolate.get('alert_id'):  # check if we're not dealing with reanalysis/resequencing
                                    self.___insert_item_into_alerts(threshold_key.split('_')[-1],
                                                                    investigation_method, subject_isolate_tuple,
                                                                    cgsts, distance_threshold,
                                                                    sliding_windows_by_weight[0][1].strftime('%Y-%m-%d'),
                                                                    sliding_windows_by_weight[0][2].strftime('%Y-%m-%d'))
                                else:
                                    if threshold_key == 'threshold_alert' and \
                                            isolate.get('previous_version_alert_type') == 'warning':
                                        self.___update_warning_to_alert(str(isolate['alert_id']),
                                                                        str(distance_threshold))
                                    self.___update_variable_details_for_alert(
                                        str(isolate['alert_id']), cgsts,
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
                                    queried_isolates = self._isolates_psql_tbl.select_isolates_by_cluster_group(
                                        (self._bigsdb_config_data['alerts'][self._species][
                                             f'threshold_warning_classification_scheme_id'],
                                         self._cgmlst_bigsdb_scheme_id, isolate['cgST']))
                                    for isolate_tuple in queried_isolates:
                                        if isolate_tuple[1] == isolate['isolate_name']:
                                            subject_isolate_tuple = isolate_tuple
                                            self._subject_isolates_tuples.add(subject_isolate_tuple)
                                break
                    else:
                        self._subject_isolates_tuples.add(queried_isolates[0])

    def __evaluate_warning_and_alert_for_affected_isolates(self, investigation_method) -> None:
        """
        Part 3:
        Evaluate alerts for affected isolates.
        :param investigation_method: distance matrix or single linkage
        :return: None
        """
        for affected_isolate_tuple in self._affected_isolates_tuples:
            affected_bigsdb_id = affected_isolate_tuple[0]
            affected_isolate_name = affected_isolate_tuple[1]  # unused, but keeping here for clarity
            affected_isolation_date = affected_isolate_tuple[2]
            affected_cgst = affected_isolate_tuple[3]
            if investigation_method == 'single linkage':
                affected_clgr = affected_isolate_tuple[4]

            # extract row from distance matrix
            row_cgst = self._distance_matrix[affected_cgst - 1]
            # order of keys below is important, if alert is triggered we'll break because warning will be redundant
            for threshold_key in ['threshold_alert', 'threshold_warning']:
                distance_threshold = self._bigsdb_config_data['alerts'][self._species][threshold_key]
                # get all cgSTs within distance, includes self
                indices = np.where(row_cgst <= distance_threshold)[0]
                cgsts = [x + 1 for x in indices]
                cgsts_as_tuple_of_str = tuple(str(x + 1) for x in indices)

            with TblIsolates(self._species) as self._isolates_psql_tbl:
                if self._timeframe_is_infinite:
                    if investigation_method == 'distance matrix':
                        if not self._cgst_isolatecount_dict.get(affected_cgst):
                            queried_isolates = self._isolates_psql_tbl.select_isolates_by_cgsts(
                                (self._cgmlst_bigsdb_scheme_id, cgsts_as_tuple_of_str))
                            self._cgst_isolatecount_dict[affected_cgst] = len(queried_isolates)

                        queried_isolates_number = self._cgst_isolatecount_dict[affected_cgst]
                    elif investigation_method == 'single linkage':
                        if not self._clgr_isolatecount_dict.get(affected_clgr):
                            queried_isolates = self._isolates_psql_tbl.select_isolates_by_cluster_group(
                                (self._bigsdb_config_data['alerts'][self._species][
                                     f'{threshold_key}_classification_scheme_id'],
                                 self._cgmlst_bigsdb_scheme_id, affected_cgst))
                            # all cluster groups are the same in the query; take 4th element (cluster group) of first
                            # tuple, which always has to exist because the isolate itself is definitely queried)
                            self._clgr_isolatecount_dict[queried_isolates[0][4]] = len(queried_isolates)

                        queried_isolates_number = self._clgr_isolatecount_dict[affected_clgr]
                else:
                    analysis_date = affected_isolation_date
                    timedelta_timeframe = datetime.timedelta(
                        days=(self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] * 31))
                    start_date = (analysis_date - timedelta_timeframe).strftime('%Y-%m-%d')
                    end_date = (analysis_date + timedelta_timeframe).strftime('%Y-%m-%d')
                    if investigation_method == 'distance matrix':
                        if not self._cgst_date_isolatecount_dict.get((affected_cgst, affected_isolation_date)):
                            queried_isolates = self._isolates_psql_tbl.select_isolates_by_cgsts_and_between_dates(
                                (self._cgmlst_bigsdb_scheme_id, cgsts_as_tuple_of_str, start_date, end_date))
                            self._cgst_date_isolatecount_dict[(affected_cgst, analysis_date)] = \
                                len(queried_isolates)

                        queried_isolates_number = self._cgst_date_isolatecount_dict[
                            (affected_cgst, affected_isolation_date)]
                    elif investigation_method == 'single linkage':
                        if not self._clgr_date_isolatecount_dict.get((affected_clgr, affected_isolation_date)):
                            queried_isolates = self._isolates_psql_tbl.\
                                select_isolates_by_cluster_group_and_between_dates(
                                    (self._bigsdb_config_data['alerts'][self._species][
                                         f'{threshold_key}_classification_scheme_id'],
                                     self._cgmlst_bigsdb_scheme_id, affected_cgst, start_date, end_date))
                            self._clgr_date_isolatecount_dict[(affected_clgr, analysis_date)] = \
                                len(queried_isolates)

                        queried_isolates_number = self._clgr_date_isolatecount_dict[
                            (affected_clgr, affected_isolation_date)]
            if queried_isolates_number >= self._bigsdb_config_data['alerts'][self._species]['number_of_cases']:
                with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl:
                    warning_or_alert_info = isolates_alertsdet_psql_tbl.select_alert_for_isolate(
                        (str(affected_bigsdb_id), investigation_method))
                if self._timeframe_is_infinite:
                    if len(warning_or_alert_info) == 0:
                        self.___insert_item_into_alerts(threshold_key.split('_')[-1], investigation_method,
                                                        affected_isolate_tuple, cgsts, distance_threshold)
                    else:
                        alert_id = warning_or_alert_info[0][0]
                        warning_or_alert = warning_or_alert_info[0][1]
                        if warning_or_alert == 'alert':
                            # because of the threshold_alert break of this for loop, it is never possible
                            # that we're evaluating a warning where the bigsdb db would be displaying an alert,
                            # therefore this condition is not checked here.
                            # in Any possible case, update the variable details for a warning or alert,
                            # it is not worth it to check if they changed
                            self.___update_variable_details_for_alert(
                                str(alert_id), cgsts, investigation_method, warning_or_alert, start_date, end_date,
                                subject_clgr=affected_clgr if investigation_method == 'single linkage' else None)
                        elif warning_or_alert == 'warning':
                            # Here we need to make the distinction between threshold_alert and threshold_warning;
                            # only if the threshold_key is alert we'll change the status and type,
                            # else only the contents
                            if threshold_key == 'threshold_alert':
                                # Update alerts table to evolve from warning to alert
                                self.___update_warning_to_alert(str(alert_id), str(distance_threshold))
                            # in Any possible case, update the variable details for a warning or alert,
                            # it is not worth it to check if they changed
                            self.___update_variable_details_for_alert(
                                str(alert_id), cgsts, investigation_method, warning_or_alert,
                                subject_clgr=affected_clgr if investigation_method == 'single linkage' else None)

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
                    sliding_windows_by_weight: List[Tuple[float, datetime.date, datetime.date]] = []
                    for window_start, window_end in zip(
                            self.loop_over_days(affected_isolation_date - timedelta_timeframe, affected_isolation_date),
                            self.loop_over_days(affected_isolation_date, affected_isolation_date + timedelta_timeframe)):
                        isolates_count = 0
                        isolates_weight = 0
                        for queried_isolate in queried_isolates:
                            if window_start <= queried_isolate[2] <= window_end:
                                isolates_count += 1
                                isolates_weight += 1 / abs((affected_isolation_date - queried_isolate[2]).days) if (affected_isolation_date - queried_isolate[2]).days != 0 else 1
                        if isolates_count >= self._bigsdb_config_data['alerts'][self._species]['number_of_cases']:
                            sliding_windows_by_weight.append((isolates_weight, window_start, window_end))
                    if len(sliding_windows_by_weight) == 0:
                        # No sliding windows meeting the threshold were found
                        continue
                    # sort the sliding windows so that the weights and dates are sorted in descending order
                    sliding_windows_by_weight.sort(reverse=True)
                    if len(warning_or_alert_info) == 0:
                        self.___insert_item_into_alerts(threshold_key.split('_')[-1], investigation_method,
                                                        affected_isolate_tuple, cgsts, distance_threshold,
                                                        sliding_windows_by_weight[0][1].strftime('%Y-%m-%d'),
                                                        sliding_windows_by_weight[0][2].strftime('%Y-%m-%d'))
                    else:
                        alert_id = warning_or_alert_info[0][0]
                        warning_or_alert = warning_or_alert_info[0][1]
                        if warning_or_alert == 'alert':
                            # because of the threshold_alert break of this for loop, it is never possible
                            # that we're evaluating a warning where the bigsdb db would be displaying an alert,
                            # therefore this condition is not checked here.
                            # in Any possible case, update the variable details for a warning or alert,
                            # it is not worth it to check if they changed
                            self.___update_variable_details_for_alert(
                                str(alert_id), cgsts, investigation_method, warning_or_alert,
                                sliding_windows_by_weight[0][1].strftime('%Y-%m-%d'),
                                sliding_windows_by_weight[0][2].strftime('%Y-%m-%d'),
                                subject_clgr=affected_clgr if investigation_method == 'single linkage' else None)
                        elif warning_or_alert == 'warning':
                            # Here we need to make the distinction between threshold_alert and threshold_warning;
                            # only if the threshold_key is alert we'll change the status and type,
                            # else only the contents
                            if threshold_key == 'threshold_alert':
                                # Update alerts table to evolve from warning to alert
                                self.___update_warning_to_alert(str(alert_id), str(distance_threshold))
                            # in Any possible case, update the variable details for a warning or alert,
                            # it is not worth it to check if they changed
                            self.___update_variable_details_for_alert(
                                str(alert_id), cgsts, investigation_method, warning_or_alert,
                                sliding_windows_by_weight[0][1].strftime('%Y-%m-%d'),
                                sliding_windows_by_weight[0][2].strftime('%Y-%m-%d'),
                                subject_clgr=affected_clgr if investigation_method == 'single linkage' else None)
                if threshold_key == 'threshold_alert':
                    # if Alert is triggered, break the for loop because a warning would be redundant
                    break

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
                                   cgsts: List[int], threshold: int, start_date: str = None,
                                   end_date: str = None) -> None:
        """
        Inserts a new alert/warning (=type) into the alerts table, and its details in the alert_details table
        :param alert_type: warning/alert
        :param investigation_method: distance matrix or single linkage
        :param subject_isolate_tuple: subject isolate tuple containing bigsdb_id, isolate name, isolation date, and
        the cgst of the subject
        :param cgsts: involved cgsts for this particular subject
        :param threshold: threshold; pathogen-specific threshold associated with the alert/warning
        :param start_date: str in YYYY-MM-DD format, pathogen specific timeframe start date
        :param end_date: str in YYYY-MM-DD format, pathogen specific timeframe end date
        :return: None
        """
        # unpack psql output tuple
        subject_bigsdb_id = subject_isolate_tuple[0]
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
                 f'{subject_bigsdb_id}" target="_blank">{subject_isolate_name}</a></p>'))
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
                cgsts_plaintext = '","'.join(str(x) for x in cgsts)
                if self._timeframe_is_infinite:
                    url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
                else:
                    url = f'generateUrlCgstDate("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ' \
                          f'["{cgsts_plaintext}"], "{start_date}", "{end_date}")'
            elif investigation_method == 'single linkage':
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
                cgsts_as_str = ','.join(str(x) for x in cgsts)
                url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
                isolates_alertsdet_psql_tbl.insert_alert_metadata(
                    ('cgsts time independent',
                     f'<div id="{cgsts_as_str}"><script type="text/javascript">addUrlToField({url}, '
                     f'"{cgsts_as_str}")</script>'))
                isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('cgsts time independent', 5))
            elif investigation_method == 'single linkage':
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
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('isolate_id', subject_bigsdb_id))

    def ___update_variable_details_for_alert(self, alert_id: str, cgsts: List[int], investigation_method: str,
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
            cgsts_plaintext = '","'.join(str(x) for x in cgsts)

            if investigation_method == 'distance matrix':
                # insert all isolates with query cgsts, independent of timeframe
                cgsts_as_str = ','.join(str(x) for x in cgsts)
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
            elif investigation_method == 'single linkage':
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
