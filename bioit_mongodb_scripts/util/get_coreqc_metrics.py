import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, Optional

PYTHONPATH = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PYTHONPATH))

from bioit_mongodb_scripts.config import COREQC_CONFIG
from bioit_mongodb_scripts.util.python_utility_functions import load_config


class GetCoreQCMetrics:
    """
    This class contains the function that gets the core quality metrics for a specific sample dependent on
    original_input_format, reads_input_type, and species.
    """
    def __init__(self, species: str, original_input_format: Optional[Literal['fastq', 'fasta']] = None,
                 reads_input_type: Optional[Literal['illumina', 'R9', 'R10']] = None) -> None:
        """
        Initialises this class.
        :param species: commonly used bioit species name: either genus or specific like stec
        :param original_input_format: original input that was given to run the first analysis
        :param reads_input_type: if the original_input_format is fastq, which type is it?; 'illumina', 'R9', 'R10'
        :return: None
        """
        self._species = species
        self._original_input_format = original_input_format
        self._reads_input_type = reads_input_type

        self._coreqc_config = load_config(COREQC_CONFIG)

    def get_sample_coreqc_metrics(self) -> dict[str, Any]:
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

        # Remove all checks that are not available for fasta so that check_coreqc_metrics doesn't have to do this.
        if self._original_input_format == 'fasta':
            for key, metric_info in deepcopy(sample_coreqc_metrics).items():
                if not metric_info['available_for_fasta_input']:
                    sample_coreqc_metrics.pop(key)

        self.__convert_iterations_to_separate_keys(sample_coreqc_metrics)

        return sample_coreqc_metrics

    def __choose_average_quality_score_metric(self, pathogen_metrics_thresholds: dict[str, dict[str, float]]) -> None:
        """
        Chooses the correct average quality score metric based on the read_input_type and removes the others in place.
        :param pathogen_metrics_thresholds: core quality metrics and thresholds for current pathogen, to be modified in
        place.
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

    @staticmethod
    def __convert_iterations_to_separate_keys(sample_coreqc_metrics: dict[str, Any]) -> None:
        """
        For Influenza, for many segments the same thresholds need to be checked, therefore in order to keep the config
        clean, an iterate variable is used. This iterate variable is consumed in this function to separate all
        iterations with the same configuration.
        :param sample_coreqc_metrics: core quality metrics and thresholds for current sample, to be modified in place.
        :return: None
        """
        for key, metric_info in deepcopy(sample_coreqc_metrics).items():
            iterations = metric_info.get('iterate')
            if iterations:
                # pop iterate from metric_info to clean dictionary a bit
                metric_info.pop('iterate')
                # store field & parameter_name in order to keep their original values for all iterations
                field = metric_info['field']
                parameter_name = metric_info['parameter_name']
                for iteration in iterations:
                    metric_info['field'] = field.replace('iterate', iteration)
                    metric_info['parameter_name'] = parameter_name.replace('iterate', iteration)
                    # add separated iteration to sample_coreqc_metrics dictionary
                    sample_coreqc_metrics[f"{key}_{iteration}"] = metric_info
                sample_coreqc_metrics.pop(key)
