import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import COREQC_CONFIG
from bioit_mongodb_scripts.model.json_model import JsonReportDict
from bioit_mongodb_scripts.util.mongo_initialisation import MongoInitialisation
from bioit_mongodb_scripts.util.python_utility_functions import get_mongodb_config_data, load_config


class CheckCoreQCMetrics:
    """
    This class contains the function that checks the core quality metrics.
    """
    def __init__(self, technical_id: str, json_report: JsonReportDict, species: str, reportdirectorypath: Path, 
                 original_input_format: Optional[Literal['fastq', 'fasta']] = None, 
                 mongo_config_data: dict[str, Any] = None,
                 reads_input_type: Optional[Literal['illumina', 'R9', 'R10']] = None) -> None:
        """
        Initialises this class.
        :param technical_id: sample id/ isolates id
        :param self._json_report: json dict containing all results which are found under the 'results' key
        :param species: commonly used bioit species name: either genus or specific like stec
        :param reportdirectorypath: absolute path to where the directory containing all files required for html are 
            stored (only required for new_isolate)
        :param original_input_format: original input that was given to run the first analysis
        :param mongo_config_data: Use provided mongo_config_data, else get mongo_config_data from file
        :param reads_input_type: if the original_input_format is fastq, which type is it?; 'illumina', 'R9', 'R10'
        :return: None
        """
        self._technical_id = technical_id
        self._json_report = json_report
        self._species = species
        self._reportdirectorypath = reportdirectorypath
        self._original_input_format = original_input_format
        self._mongo_config_data = mongo_config_data if mongo_config_data else get_mongodb_config_data()
        self._reads_input_type = reads_input_type
        
        # Add class variables
        self._coreqc_config = load_config(COREQC_CONFIG)
        self._rejection_reasons = {}
        self._good_sample_quality = True

    def check_coreqc_metrics(self) -> bool:
        """
        This function checks the core quality metrics. If any failure threshold is surpassed, then the isolate is added
        to the isolates_rejected_coreqc collection and the script is stopped.
        If no failure threshold is surpassed, but any warning threshold is, then the function returns False.
        If no failure or warning thresholds are exceeded, then the function returns True.
        The core quality metrics used here, and found in the corresponding COREQC_CONFIG originate from the
        D8.1_HERA_BE_WGS_Updated_quality_guidelines_report_29NOV2024 document that can be found in the HERA folder.
        :return: Whether the input document is of good quality according to the core quality metrics (good quality =
        does not surpass any warning threshold)
        """
        sample_coreqc_metrics = self._get_sample_coreqc_metrics()
        for metric, metric_info in sample_coreqc_metrics.items():
            # For Influenza, for many segments the same thresholds need to be checked, in order to keep the config
            # clean, an iterate variable is used.
            iterations = metric_info.get('iterate')
            if iterations:
                for iteration in iterations:
                    self._evaluate_core_qc_metric(metric_info, metric, iteration)
            else:
                self._evaluate_core_qc_metric(metric_info, metric)

        if len(self._rejection_reasons) > 0:
            self._insert_into_rejected_isolates_collection(sample_coreqc_metrics)

        return self._good_sample_quality

    def _get_sample_coreqc_metrics(self) -> dict[str, Any]:
        """
        Gets the coreqc metrics to be checked for this sample (pathogen specific and input specific) with all
        thresholds & fields info.
        :return: The coreqc metrics to be checked for this pathogen with all thresholds & fields info.
        """
        sample_coreqc_metrics = {}
        pathogen_metrics_thresholds = self._coreqc_config['species'][self._species]
        if self._original_input_format != 'fasta':
            self.__choose_average_quality_score_metric(pathogen_metrics_thresholds)

        # Merge thresholds stored in 'species' and fields info stored in 'metrics'
        for key, values in pathogen_metrics_thresholds.items():
            sample_coreqc_metrics[key] = {**values, **self._coreqc_config['metrics'][key]}

        return sample_coreqc_metrics

    def __choose_average_quality_score_metric(self, pathogen_metrics_thresholds: dict[str, dict[str, float]]) -> None:
        """
        Chooses the correct average quality score metric based on the read_input_type and removes the others in place.
        :param pathogen_metrics_thresholds: core quality metrics and thresholds for current pathogen, to be modified in place.
        :return: None
        """
        average_quality_score_metrics_to_remove = ['average_quality_score_illumina', 'average_quality_score_ont_R9',
                                                   'average_quality_score_ont_R10']
        if self._reads_input_type == 'illumina':
            average_quality_score_metrics_to_remove.remove('average_quality_score_illumina')
        elif self._reads_input_type == 'R9':
            average_quality_score_metrics_to_remove.remove('average_quality_score_ont_R9')
        elif self._reads_input_type == 'R10':
            average_quality_score_metrics_to_remove.remove('average_quality_score_ont_R10')
        else:  # self._reads_input_type is None
            pass
        for metric_to_remove in average_quality_score_metrics_to_remove:
            pathogen_metrics_thresholds.pop(metric_to_remove)

    def _evaluate_core_qc_metric(self, metric_info: dict[str, Any], core_qc_metric: str,
                                 iteration: Optional[str] = None) -> None:
        """
        Evaluates a core qc metric.
        :param metric_info: the current metric's info
        :param core_qc_metric: the current core qc metric's name in the config.
        :param iteration: In the viral qc, certain metrics need to be iterated over multiple segments. It basically 
        works like 'field_to_replace'.
        :return: None
        """
        if not metric_info['available_for_fasta_input'] and self._original_input_format == 'fasta':
            return
        qc_value = self.__get_qcvalue_for_metric(metric_info, iteration)
        self.__evaluate_thresholds_for_qcvalue(metric_info, qc_value, core_qc_metric, iteration)
        
    def __get_qcvalue_for_metric(self, metric_info: dict[str, Any], iteration: Optional[str] = None) -> float:
        """
        Gets the quality control value as a float from the json_report. Replaces part of fields where necessary and
        strips any non-float characters where necessary. Also takes the average if necessary.
        :param metric_info: the current metric's info
        :param iteration: In the viral qc, certain metrics need to be iterated over multiple segments. It basically 
        works like 'field_to_replace'.
        :return: qc_value as float
        """
        if metric_info.get('field'):
            field = metric_info['field']
            if metric_info.get('field_to_replace'):
                for key2, value in metric_info['field_to_replace'].items():
                    field = field.replace(key2, self._json_report[value])
            elif iteration:
                field = field.replace('iterate', iteration)
            if not metric_info.get('value_format_to_strip'):
                qc_value = float(self._json_report[metric_info['category']][field])
            else:
                qc_value = float(
                    self._json_report[metric_info['category']][field].rstrip(metric_info['value_format_to_strip']))
        else:  # metric_info.get('fields'):
            qc_value = sum(
                float(self._json_report[metric_info['category']][field]) for field in metric_info['fields']) / len(
                metric_info['fields'])
        return qc_value

    def __evaluate_thresholds_for_qcvalue(self, metric_info: dict[str, Any], qc_value: float, core_qc_metric: str,
                                          iteration: Optional[str] = None):
        """
        Evaluates a given qc_value against the failure and warning thresholds for the current core quality metric.
        If the failure threshold is exceeded, then a reason is added to the rejection_reasons.
        If the warning threshold is exceeded, then the good_sample_quality is set to false.
        :param metric_info: the current metric's info
        :param qc_value: the current metric's value in the json_report that needs to be evaluated against the thresholds.
        :param core_qc_metric: the current core qc metric's name in the config.
        :param iteration: In the viral qc, certain metrics need to be iterated over multiple segments. It basically 
        works like 'field_to_replace'.
        :return: None
        """
        for threshold in ['threshold_fail', 'threshold_warn']:
            if metric_info['threshold_direction'] == 'higher':
                evaluation = float(qc_value) > metric_info[threshold]
            else:  # if metric_info['threshold_direction'] == 'lower':
                evaluation = float(qc_value) < metric_info[threshold]
            if evaluation:
                if threshold == 'threshold_fail':
                    if metric_info.get('value_format_to_strip'):
                        qc_value_formatted = f"{qc_value}{metric_info['value_format_to_strip']}"
                        threshold_formatted = f"{metric_info[threshold]}{metric_info['value_format_to_strip']}"
                    else:
                        qc_value_formatted = qc_value
                        threshold_formatted = metric_info[threshold]
                    if iteration:
                        parameter_name = metric_info['parameter_name'].replace('iterate', iteration)
                    else:
                        parameter_name = metric_info['parameter_name']
                    self._rejection_reasons[core_qc_metric] = {
                        'value': qc_value,
                        'reason': f"{parameter_name} (={qc_value_formatted}) "
                                  f"{metric_info['threshold_direction']} than allowed limit (="
                                  f"{threshold_formatted})."}
                    break
                else:  # if threshold == 'threshold_warn':
                    self._good_sample_quality = False

    def _insert_into_rejected_isolates_collection(self, sample_coreqc_metrics: dict[str, dict[str, Any]]) -> None:
        """"
        Inserts an isolate into the rejected isolates collection and includes the reasons for rejection and all quality
        sections.
        :param sample_coreqc_metrics: The current pathogen/sample's coreqc metrics.
        :return: None
        """
        # Open collections
        self._mongoinit = MongoInitialisation(self._species, mongo_config_data=self._mongo_config_data,
                                              selected_connection_string='CONNECTION_STRING_AZURE')
        isolates_rejected_coreqc_collection = self._mongoinit.initialise_isolates_rejected_coreqc_collection()

        # Logic to handle previously rejected versions of the same sample
        previous_rejected_sample_version: Optional[dict[str, Any]] = isolates_rejected_coreqc_collection.find_one(
            {'_id': self._technical_id})
        if previous_rejected_sample_version:
            previous_rejected_sample_version['isolates_id'] = self._technical_id
            previous_rejected_sample_version.pop('_id')
            isolates_rejected_coreqc_collection.insert_one(previous_rejected_sample_version)
            isolates_rejected_coreqc_collection.delete_one({'_id': self._technical_id})

        # Prepare the document that is to be inserted into the isolates_rejected_coreqc collection
        document_to_be_inserted = {
            "_id": self._technical_id,
            "report_directory": str(self._reportdirectorypath),
            "rejection_reasons": self._rejection_reasons,
            "creation_date": datetime.now(timezone.utc),
            "insertion_type": 'automatic'}
        # Quality control metrics are spread in 3 sections: quast, quality_checks and preprocess. We decided to
        # keep track of all quality sections for potential post hoc analyses.
        quality_sections = set(metric_info['category'] for metric_info in sample_coreqc_metrics.values())
        for quality_section in quality_sections:
            document_to_be_inserted[quality_section] = self._json_report[quality_section]

        isolates_rejected_coreqc_collection.insert_one(document_to_be_inserted)
        logging.info(f"Sample {self._technical_id} failed one or more core QC checks. It was added to the "
                     f"isolates_rejected_coreqc collection.")
        # exit gracefully
        sys.exit()
