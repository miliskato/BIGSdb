import datetime
import logging
import numpy as np
import socket
from typing import Any, Dict, List, Optional, Tuple, Union

from bioit_bigsdb_scripts.components.psql import TblEavTextHidden, TblEavText, TblIsolates, TblHistory, TblSequenceBin, TblSeqBinStats, TblProjectMembers, TblEavFields, TblSchemes, TblAlerts, TblAlertDetails, TblAlertDetailsFieldOrder
from bioit_bigsdb_scripts.components.python_utility_functions import get_bigsdb_config_data

class AlertsToBigs:
    # todo need to be able to have all the new ones at the same time in order to not have to reevaluate previous sliding windows multiple times # done

    # todo evaluate all new ones first # done

    # todo then evaluate all old ones within timeframe of new ones using sliding windows;
        # todo but for the old ones; how to evaluate whether already inserted or not?


    # todo !!!!!!!!!!!!!!!
    # todo how to deal with changing cgsts across resequencings and reanalyses?
    def __init__(self, list_of_isolates_inserted_in_bigsdb: List[Dict[str, Union[str, int]]], species: str, cgmlst_bigsdb_scheme_id: int) -> None:  # todo docstring
        """
        :param species: commonly used bioit species name: either genus or specific like stec
        :param sample_output_dict: results of sample
        :return: None
        """
        self._list_of_isolates_inserted_in_bigsdb = list_of_isolates_inserted_in_bigsdb
        self._species = species
        self._cgmlst_bigsdb_scheme_id = cgmlst_bigsdb_scheme_id
        self._bigsdb_config_data = get_bigsdb_config_data()
        if not self._bigsdb_config_data['alerts'].get(self._species):
            return
        self._distance_matrix: np.array = np.load(str(self._bigsdb_config_data['naive_clustering_distance_matrix_file']).
                                                  replace('species', self._species))
        self._cgst_isolatecount_dict: Dict[int, int] = {}
        self._cgst_date_isolatecount_dict: Dict[tuple[int, str], int] = {}
        self._affected_isolates_tuples: set[Tuple[Any], ...] = set()
        self._subject_isolates_tuples: set[Tuple[Any], ...] = set()

        self._evaluate_warning_and_alert_from_distance_matrix()

    def _evaluate_warning_and_alert_from_distance_matrix(self) -> None:  # todo mk docstring
        """
        Evaluates whether the currently inserted isolate triggers a warning or an alert and inserts it if needed
        :return: None
        """
        logging.info('Computing warnings/alerts for isolates just inserted into bigsdb')
        investigation_method = 'distance_matrix'
        for isolate in self._list_of_isolates_inserted_in_bigsdb:
            if isolate['cgST'] is None:
                continue

            # extract row from distance matrix
            row_cgst = self._distance_matrix[isolate['cgST'] - 1]
            # with TblSchemes(self._species, 'isolates') as isolates_schemes_psql_tbl:
            #     cgmlst_bigsdb_scheme_id = isolates_schemes_psql_tbl.select_scheme_id_cgmlst()[0][0]
            for threshold_key in ['threshold_alert',
                                  'threshold_warning']:  # order is important, if alert is triggered we'll break because warning will be redundant
                distance_threshold = self._bigsdb_config_data['alerts'][self._species][threshold_key]
                # get all cgSTs within distance, includes self
                indices = np.where(row_cgst <= distance_threshold)[0]
                cgsts = [x + 1 for x in indices]
                cgsts_as_tuple_of_str = tuple(str(x + 1) for x in indices)

                with TblIsolates(self._species) as self.isolates_psql_tbl:
                    if self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] > 10000:
                        queried_isolates = self.isolates_psql_tbl.select_isolates_by_cgsts((self._cgmlst_bigsdb_scheme_id,
                                                                                            self._cgmlst_bigsdb_scheme_id,
                                                                                            self._cgmlst_bigsdb_scheme_id,
                                                                                            cgsts_as_tuple_of_str))
                        self._cgst_isolatecount_dict[isolate['cgST']] = len(queried_isolates)
                    else:
                        analysis_date = datetime.datetime.strptime(isolate['isolation_date'], '%d/%m/%Y - %X')
                        timedelta_timeframe = datetime.timedelta(days=(self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] * 31))
                        start_date = (analysis_date - timedelta_timeframe).strftime('%Y-%m-%d')
                        end_date = (analysis_date + timedelta_timeframe).strftime('%Y-%m-%d')
                        queried_isolates = self.isolates_psql_tbl.select_isolates_by_cgsts_and_between_dates((self._cgmlst_bigsdb_scheme_id,
                                                                                                              self._cgmlst_bigsdb_scheme_id,
                                                                                                              self._cgmlst_bigsdb_scheme_id,
                                                                                                              cgsts_as_tuple_of_str,
                                                                                                              start_date,
                                                                                                              end_date))
                        self._cgst_date_isolatecount_dict[(isolate['cgST'], analysis_date.strftime('%Y-%m-%d'))] = len(queried_isolates)
                    if len(queried_isolates) > 1:
                        subject_isolate_tuple = None
                        for isolate_tuple in queried_isolates:
                            self._affected_isolates_tuples.add(isolate_tuple)  # todo need to in the end remember to remove tuples from the _list_of_isolates_inserted_in_bigsdb to not reeavaluate them
                            if isolate_tuple[1] == isolate['isolate_name']:
                                subject_isolate_tuple = isolate_tuple
                                self._subject_isolates_tuples.add(subject_isolate_tuple)
                        if subject_isolate_tuple is None:
                            exceptionmessage = f"While evaluating alerts, the tuple for the subject isolate {isolate['isolate_name']} was not found in the output of the sql query."
                            logging.error(exceptionmessage)
                            raise Exception(exceptionmessage)
                        # Assess whether number of cases threshold was surpassed
                        if len(queried_isolates) >= self._bigsdb_config_data['alerts'][self._species]['number_of_cases']:
                            if self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] > 10000:
                                self.__insert_item_into_alerts(threshold_key.split('_')[-1], investigation_method, subject_isolate_tuple, cgsts, distance_threshold)
                            else:
                                self.__insert_item_into_alerts(threshold_key.split('_')[-1], investigation_method, subject_isolate_tuple, cgsts, distance_threshold, start_date, end_date)
                            if threshold_key == 'threshold_alert':
                                # if Alert is triggered, break the for loop because a warning would be redundant
                                break
                    else:
                        self._subject_isolates_tuples.add(queried_isolates[0])

            # Remove subject isolate tuples from affected ones in order to not reevaluate them
            self._affected_isolates_tuples.difference_update(self._subject_isolates_tuples)


            # with TblEavText(self._species) as isolates_eavt_psql_tbl:
            #     isolates_eavt_psql_tbl.insert_eav_id((str(isolate_id), field[0], html))
            # todo Q; i will have a field which says which isolate triggered, but if multiple subsequent isolates trigger the same warning, or if the warning evolves into an alert; should i have a check to remove previous warnings/alerts?
    
            # todo if triggered, then break the for loop

    def __insert_item_into_alerts(self, type, method, subject_isolate_tuple, cgsts, threshold, start_date = None, end_date = None): # todo docstring

        # unpack psql output tuple
        subject_bigsdb_id = subject_isolate_tuple[0]
        subject_isolate_name = subject_isolate_tuple[1]
        subject_isolation_date = subject_isolate_tuple[2]
        subject_cgst = subject_isolate_tuple[3]

        # insert into alerts table
        with TblAlerts(self._species) as isolates_alerts_psql_tbl:
            isolates_alerts_psql_tbl.insert_alert((type, method))

        # insert into alert_details and alert_details_field_order tables
        with TblAlertDetails(self._species) as isolates_alertsdet_psql_tbl, \
                TblAlertDetailsFieldOrder(self._species) as isolates_alertsdetfo_psql_tbl:

            # insert trigger subject with href
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('trigger', f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?page=info&db=bigsdb_{self._species}_isolates&id={subject_bigsdb_id}" target="_blank">{subject_isolate_name}</a></p>'))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger', 1))

            # insert trigger subject isolation date
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('trigger_isolation_date', subject_isolation_date))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger_isolation_date', 2))

            # insert trigger subject cgst with href
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('trigger_cgst', f'<p><a href="/cgi-bin/bigsdb/bigsdb.pl?page=query&submit=1&db=bigsdb_{self._species}_isolates&designation_value1={subject_cgst}&designation_field1=s_{self._cgmlst_bigsdb_scheme_id}_cgST" target="_blank">{subject_cgst}</a></p>'))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger_cgst', 3))

            # insert all trigger subjects with javascript href
            cgsts_plaintext = '","'.join(str(x) for x in cgsts)
            if self._bigsdb_config_data['alerts'][self._species]['timeframe_in_months'] > 10000:
                url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
            else:
                url = f'generateUrlCgstDate("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"], "{start_date}", "{end_date})'
            html_element = f'<div id="trigger_subjects"><script type="text/javascript">replaceQueriedValue({url}, ' \
                           f'"trigger_subjects")</script>'

            isolates_alertsdet_psql_tbl.insert_alert_metadata(('trigger_subjects', html_element))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('trigger_subjects', 4))

            # insert all isolates with query cgsts, independent of timeframe
            cgsts_as_str = ','.join(str(x) for x in cgsts)
            url = f'generateUrlCgst("{self._species}", "{self._cgmlst_bigsdb_scheme_id}", ["{cgsts_plaintext}"])'
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('cgsts_time_independent', f'<div id="{cgsts_as_str}"><script type="text/javascript">addUrlToField({url}, "{cgsts_as_str}")</script>'))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('cgsts_time_independent', 5))

            # insert threshold for information
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('cgmlst_threshold', str(threshold)))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('cgmlst_threshold', 6))

            # insert threshold for information
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('method', method))
            isolates_alertsdetfo_psql_tbl.insert_alert_details_indices(('method', 7))

            # insert isolate id for backend information; don't add it to the field order and it will not be shown in the gui
            isolates_alertsdet_psql_tbl.insert_alert_metadata(('isolate_id', subject_bigsdb_id))
