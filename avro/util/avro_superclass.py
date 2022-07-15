import abc

class Avro_superclass(object, metaclass=abc.ABCMeta):
    """
    Superclass for Avro
    """
    def __init__(self):
        self._species_options = ["listeria", "salmonella", "mycobacterium", "stec", "neisseria"]
        self._common_output_arguments = {
            "downsampling": ['downsampling_coverage_estimated', 'downsampling_coverage_target',
                             'downsampling_downsample_factor', 'downsampling_mean_read_length',
                             'downsampling_nb_read_pairs_in', 'downsampling_nb_read_pairs_out',
                             'downsampling_size_ref_genome', 'downsampling_total_bases'],
            "trimming": ['trimming_pairs_in', 'trimming_pairs_out', 'trimming_fwd_only_surviving',
                         'trimming_rev_only_surviving', 'trimming_pairs_both_dropped'],
            "assembly": ['assembly_n50', 'assembly_nb_contigs', 'assembly_total_length'],
            "qc_fastqc": ['qc_fqc_avg_qual_fwd_status', 'qc_fqc_avg_qual_fwd_value', 'qc_fqc_avg_qual_rev_status',
                          'qc_fqc_avg_qual_rev_value', 'qc_fqc_gc_fwd_status', 'qc_fqc_gc_fwd_value',
                          'qc_fqc_gc_rev_status', 'qc_fqc_gc_rev_value', 'qc_fqc_n_fraction_fwd_status',
                          'qc_fqc_n_fraction_fwd_value', 'qc_fqc_n_fraction_rev_status', 'qc_fqc_n_fraction_rev_value',
                          'qc_fqc_per_base_fwd_status', 'qc_fqc_per_base_fwd_value', 'qc_fqc_per_base_rev_status',
                          'qc_fqc_per_base_rev_value', 'qc_fqc_qscore_fwd_status', 'qc_fqc_qscore_fwd_value',
                          'qc_fqc_qscore_rev_status', 'qc_fqc_qscore_rev_value', 'qc_fqc_seq_len_fwd_status',
                          'qc_fqc_seq_len_fwd_value', 'qc_fqc_seq_len_rev_status', 'qc_fqc_seq_len_rev_value'],
            "qc_cgmlst": ['qc_cgmlst_status', 'qc_cgmlst_value'],
            "qc_assembly": ['qc_cov_assembly_status', 'qc_cov_assembly_value', 'qc_map_rate_assembly_status',
                            'qc_map_rate_assembly_value'],
            "qc_reference": ['qc_cov_ref_status', 'qc_cov_ref_value', 'qc_map_rate_ref_status', 'qc_map_rate_ref_value'],
            "qc_kraken": ['qc_kraken_status', 'qc_kraken_value'],
            "kraken": ['kraken2_expected_species', 'kraken2_expected_species_occurrence', 'kraken2_contaminants_warn',
                       'kraken2_contaminants_fail'],
            "variant_calling": ['vc-mapping_rate', 'vc-median_depth'],
            "variant_filtering": ['filt-depth-in', 'filt-depth-out', 'filt-distance-in', 'filt-distance-out',
                                  'filt-mapping_qual-in', 'filt-mapping_qual-out', 'filt-region-in', 'filt-region-out',
                                  'filt-snp_qual-in', 'filt-snp_qual-out', 'filt-zscore-in', 'filt-zscore-out']
        }

    def _make_int_if_possible(self, value):
        """
        Converts (string) to int if possible
        Function is used because for e.g. allele designations or ST, the result can be - as well as int, and reading from tsv is always string.
        :param value: inputvalue(/string)
        """
        import re
        return int(value) if re.match('^[0-9]+$', value) else value