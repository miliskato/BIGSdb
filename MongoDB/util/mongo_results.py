import os
import logging
from pathlib import Path
import abc
from datetime import datetime
import re


class Mongoresults(object, metaclass=abc.ABCMeta):
    """
    Class for creating Mongo Schemas
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
            "qc_reference": ['qc_cov_ref_status', 'qc_cov_ref_value', 'qc_map_rate_ref_status',
                             'qc_map_rate_ref_value'],
            "qc_kraken": ['qc_kraken_status', 'qc_kraken_value'],
            "kraken": ['kraken2_expected_species', 'kraken2_expected_species_occurrence', 'kraken2_contaminants_warn',
                       'kraken2_contaminants_fail'],
            "variant_calling": ['vc-mapping_rate', 'vc-median_depth'],
            "variant_filtering": ['filt-depth-in', 'filt-depth-out', 'filt-distance-in', 'filt-distance-out',
                                  'filt-mapping_qual-in', 'filt-mapping_qual-out', 'filt-region-in', 'filt-region-out',
                                  'filt-snp_qual-in', 'filt-snp_qual-out', 'filt-zscore-in', 'filt-zscore-out']
        }
        logging.info("Mongosresults initialised")

    def parse_output(self, species: str, outputtsvfile: Path) -> dict:
        """
        Parses the tsv ouputfile into a dict
        :param species: species will decide the schema to be used to parse the outputfile
        :param outputtsvfile: path to the file
        :return: dictionary of the tsv's values
        """
        # Parse output
        outputtsvdict = {}
        handle = open(outputtsvfile, "r").readlines()
        for line in handle:
            outputtsvdict[line.split("\t")[0]] = line.split("\t")[1].strip("\n")
        logging.info(f'Treating sample : {outputtsvdict["sample"]}')

        return self._species_selection(species, outputtsvdict)

    def _parse_date_to_iso(self, str_date: str):
        split_date = re.split('/|-|:', str_date.replace(' ', ''))
        split_date = [int(i) for i in split_date]
        new_date = datetime(split_date[2], split_date[1], split_date[0], split_date[3], split_date[4], split_date[5])
        return new_date

    def _species_selection(self, species: str, outputtsvdict: dict) -> dict:
        """
        Parses the outputtsv according to species
        :param species: species
        :param outputtsvdict: dict
        :return: Reformatted dict
        """
        records = []
        species = str(species)
        if species in self._species_options:
            logging.info(f"species {species} in allowed species")
            if species == "listeria":
                # records needs to be a list for fastavro (even though only one sample at a time in our case)
                records = {"isolate": outputtsvdict["sample"],
                           "pipeline_version": outputtsvdict["pipeline_version"],
                           "analysis_date": self._parse_date_to_iso(outputtsvdict["analysis_date"]),
                           "downsampling": self._avro_input_commontsvoutput(outputtsvdict, "downsampling"),
                           "trimming": self._avro_input_commontsvoutput(outputtsvdict, "trimming"),
                           "assembly": self._avro_input_commontsvoutput(outputtsvdict, "assembly"),
                           "qc":
                               {"qc_fastqc": self._avro_input_commontsvoutput(outputtsvdict, "qc_fastqc"),
                               "qc_cgmlst": self._avro_input_commontsvoutput(outputtsvdict, "qc_cgmlst"),
                               "qc_assembly": self._avro_input_commontsvoutput(outputtsvdict, "qc_assembly"),
                               "qc_kraken": self._avro_input_commontsvoutput(outputtsvdict, "qc_kraken")
                                },
                           "kraken": self._avro_input_commontsvoutput(outputtsvdict, "kraken"),
                           "mlst": self._avro_input_typingschema(species, "mlst", "mlst", outputtsvdict),
                           "cgmlst": self._avro_input_typingschema(species, "cgmlst", "cgmlst", outputtsvdict),
                           "pcr_serogroup": self._avro_input_typingschema(species, "pcr_serogroup", "serogroup",
                                                                          outputtsvdict),
                           'typing_virulence': self._avro_input_typingschema(species, 'typing_virulence', 'virulence',
                                                                             outputtsvdict),
                           'typing_amr': self._avro_input_typingschema(species, 'typing_amr', 'antibiotic_resistance',
                                                                       outputtsvdict),
                           'species_confirmation': self._avro_input_typingschema(species, 'species_confirmation',
                                                                                 'species_confirmation', outputtsvdict),
                           'metal_detergent': self._avro_input_typingschema(species, 'metal_detergent',
                                                                            'metal_detergent_resistance',
                                                                            outputtsvdict),
                           "hits_ncbi_amr": outputtsvdict["hits_ncbi_amr"],
                           "hits_resfinder": outputtsvdict["hits_resfinder"],
                           "hits_virulencefinder": outputtsvdict["hits_virulencefinder"],
                           "hits_plasmidfinder": outputtsvdict["hits_plasmidfinder"],
                           "hits_vfdb_core": outputtsvdict["hits_vfdb_core"]
                           }

            elif species == "mycobacterium":
                self._common_output_arguments["csb_rd"] = ['csb_detected', 'RD1_detected', 'RD9_detected']
                self._common_output_arguments["51SNP"] = ['51SNP-positive_control', '51SNP-gyrB_group',
                                                          '51SNP-genetic_group', '51SNP-scg', '51SNP-st',
                                                          '51SNP-matching_snps', '51SNP-SNP01', '51SNP-SNP02',
                                                          '51SNP-SNP03', '51SNP-SNP04', '51SNP-SNP05', '51SNP-SNP06',
                                                          '51SNP-SNP07', '51SNP-SNP08', '51SNP-SNP09', '51SNP-SNP10',
                                                          '51SNP-SNP11', '51SNP-SNP12', '51SNP-SNP13', '51SNP-SNP14',
                                                          '51SNP-SNP15', '51SNP-SNP16', '51SNP-SNP17', '51SNP-SNP18',
                                                          '51SNP-SNP19', '51SNP-SNP20', '51SNP-SNP21', '51SNP-SNP22',
                                                          '51SNP-SNP23', '51SNP-SNP24', '51SNP-SNP25', '51SNP-SNP26',
                                                          '51SNP-SNP27', '51SNP-SNP28', '51SNP-SNP29', '51SNP-SNP30',
                                                          '51SNP-SNP31', '51SNP-SNP32', '51SNP-SNP33', '51SNP-SNP34',
                                                          '51SNP-SNP35', '51SNP-SNP36', '51SNP-SNP37', '51SNP-SNP38',
                                                          '51SNP-SNP39', '51SNP-SNP40', '51SNP-SNP41', '51SNP-SNP42',
                                                          '51SNP-SNP43', '51SNP-SNP44', '51SNP-SNP45', '51SNP-SNP46',
                                                          '51SNP-SNP47', '51SNP-SNP48', '51SNP-SNP49', '51SNP-SNP50',
                                                          '51SNP-SNP51']
                self._common_output_arguments["snpit"] = ['snpit_species', 'snpit_lineage', 'snpit_sublineage',
                                                          'snpit_percent_matched']
                self._common_output_arguments["spoligotyping"] = ['spoligotype_binary', 'spoligotype_octal',
                                                                  'sit_number']
                self._common_output_arguments["snp_lineage"] = ['snp_lineages']
                self._common_output_arguments["amr_who"] = ['amr_type', 'amr_first_line_resistant',
                                                            'amr_second_line_group_a_resistant',
                                                            'amr_second_line_group_b_resistant', 'amr_pheno_INH',
                                                            'amr_mutations_INH_Associated_with_R',
                                                            'amr_mutations_INH_Associated_with_R_(int.)',
                                                            'amr_mutations_INH_Not_associated_with_R',
                                                            'amr_mutations_INH_Not_associated_with_R_(int.)',
                                                            'amr_mutations_INH_Uncertain_significance',
                                                            'amr_mutations_INH_Not_in_db.', 'amr_pheno_RIF',
                                                            'amr_mutations_RIF_Associated_with_R',
                                                            'amr_mutations_RIF_Associated_with_R_(int.)',
                                                            'amr_mutations_RIF_Not_associated_with_R',
                                                            'amr_mutations_RIF_Not_associated_with_R_(int.)',
                                                            'amr_mutations_RIF_Uncertain_significance',
                                                            'amr_mutations_RIF_Not_in_db.', 'amr_pheno_LEV',
                                                            'amr_mutations_LEV_Associated_with_R',
                                                            'amr_mutations_LEV_Associated_with_R_(int.)',
                                                            'amr_mutations_LEV_Not_associated_with_R',
                                                            'amr_mutations_LEV_Not_associated_with_R_(int.)',
                                                            'amr_mutations_LEV_Uncertain_significance',
                                                            'amr_mutations_LEV_Not_in_db.', 'amr_pheno_MXF',
                                                            'amr_mutations_MXF_Associated_with_R',
                                                            'amr_mutations_MXF_Associated_with_R_(int.)',
                                                            'amr_mutations_MXF_Not_associated_with_R',
                                                            'amr_mutations_MXF_Not_associated_with_R_(int.)',
                                                            'amr_mutations_MXF_Uncertain_significance',
                                                            'amr_mutations_MXF_Not_in_db.', 'amr_pheno_AMI',
                                                            'amr_mutations_AMI_Associated_with_R',
                                                            'amr_mutations_AMI_Associated_with_R_(int.)',
                                                            'amr_mutations_AMI_Not_associated_with_R',
                                                            'amr_mutations_AMI_Not_associated_with_R_(int.)',
                                                            'amr_mutations_AMI_Uncertain_significance',
                                                            'amr_mutations_AMI_Not_in_db.', 'amr_pheno_CAP',
                                                            'amr_mutations_CAP_Associated_with_R',
                                                            'amr_mutations_CAP_Associated_with_R_(int.)',
                                                            'amr_mutations_CAP_Not_associated_with_R',
                                                            'amr_mutations_CAP_Not_associated_with_R_(int.)',
                                                            'amr_mutations_CAP_Uncertain_significance',
                                                            'amr_mutations_CAP_Not_in_db.', 'amr_pheno_KAN',
                                                            'amr_mutations_KAN_Associated_with_R',
                                                            'amr_mutations_KAN_Associated_with_R_(int.)',
                                                            'amr_mutations_KAN_Not_associated_with_R',
                                                            'amr_mutations_KAN_Not_associated_with_R_(int.)',
                                                            'amr_mutations_KAN_Uncertain_significance',
                                                            'amr_mutations_KAN_Not_in_db.', 'amr_pheno_STM',
                                                            'amr_mutations_STM_Associated_with_R',
                                                            'amr_mutations_STM_Associated_with_R_(int.)',
                                                            'amr_mutations_STM_Not_associated_with_R',
                                                            'amr_mutations_STM_Not_associated_with_R_(int.)',
                                                            'amr_mutations_STM_Uncertain_significance',
                                                            'amr_mutations_STM_Not_in_db.', 'amr_pheno_ETH',
                                                            'amr_mutations_ETH_Associated_with_R',
                                                            'amr_mutations_ETH_Associated_with_R_(int.)',
                                                            'amr_mutations_ETH_Not_associated_with_R',
                                                            'amr_mutations_ETH_Not_associated_with_R_(int.)',
                                                            'amr_mutations_ETH_Uncertain_significance',
                                                            'amr_mutations_ETH_Not_in_db.', 'amr_pheno_PZA',
                                                            'amr_mutations_PZA_Associated_with_R',
                                                            'amr_mutations_PZA_Associated_with_R_(int.)',
                                                            'amr_mutations_PZA_Not_associated_with_R',
                                                            'amr_mutations_PZA_Not_associated_with_R_(int.)',
                                                            'amr_mutations_PZA_Uncertain_significance',
                                                            'amr_mutations_PZA_Not_in_db.', 'amr_pheno_BDQ',
                                                            'amr_mutations_BDQ_Associated_with_R',
                                                            'amr_mutations_BDQ_Associated_with_R_(int.)',
                                                            'amr_mutations_BDQ_Not_associated_with_R',
                                                            'amr_mutations_BDQ_Not_associated_with_R_(int.)',
                                                            'amr_mutations_BDQ_Uncertain_significance',
                                                            'amr_mutations_BDQ_Not_in_db.', 'amr_pheno_CFZ',
                                                            'amr_mutations_CFZ_Associated_with_R',
                                                            'amr_mutations_CFZ_Associated_with_R_(int.)',
                                                            'amr_mutations_CFZ_Not_associated_with_R',
                                                            'amr_mutations_CFZ_Not_associated_with_R_(int.)',
                                                            'amr_mutations_CFZ_Uncertain_significance',
                                                            'amr_mutations_CFZ_Not_in_db.', 'amr_pheno_DLM',
                                                            'amr_mutations_DLM_Associated_with_R',
                                                            'amr_mutations_DLM_Associated_with_R_(int.)',
                                                            'amr_mutations_DLM_Not_associated_with_R',
                                                            'amr_mutations_DLM_Not_associated_with_R_(int.)',
                                                            'amr_mutations_DLM_Uncertain_significance',
                                                            'amr_mutations_DLM_Not_in_db.', 'amr_pheno_EMB',
                                                            'amr_mutations_EMB_Associated_with_R',
                                                            'amr_mutations_EMB_Associated_with_R_(int.)',
                                                            'amr_mutations_EMB_Not_associated_with_R',
                                                            'amr_mutations_EMB_Not_associated_with_R_(int.)',
                                                            'amr_mutations_EMB_Uncertain_significance',
                                                            'amr_mutations_EMB_Not_in_db.', 'amr_pheno_LZD',
                                                            'amr_mutations_LZD_Associated_with_R',
                                                            'amr_mutations_LZD_Associated_with_R_(int.)',
                                                            'amr_mutations_LZD_Not_associated_with_R',
                                                            'amr_mutations_LZD_Not_associated_with_R_(int.)',
                                                            'amr_mutations_LZD_Uncertain_significance',
                                                            'amr_mutations_LZD_Not_in_db.', 'amr_pheno_DCS',
                                                            'amr_mutations_DCS_Associated_with_R',
                                                            'amr_mutations_DCS_Associated_with_R_(int.)',
                                                            'amr_mutations_DCS_Not_associated_with_R',
                                                            'amr_mutations_DCS_Not_associated_with_R_(int.)',
                                                            'amr_mutations_DCS_Uncertain_significance',
                                                            'amr_mutations_DCS_Not_in_db.', 'amr_pheno_EFF',
                                                            'amr_mutations_EFF_Associated_with_R',
                                                            'amr_mutations_EFF_Associated_with_R_(int.)',
                                                            'amr_mutations_EFF_Not_associated_with_R',
                                                            'amr_mutations_EFF_Not_associated_with_R_(int.)',
                                                            'amr_mutations_EFF_Uncertain_significance',
                                                            'amr_mutations_EFF_Not_in_db.', 'amr_pheno_PAS',
                                                            'amr_mutations_PAS_Associated_with_R',
                                                            'amr_mutations_PAS_Associated_with_R_(int.)',
                                                            'amr_mutations_PAS_Not_associated_with_R',
                                                            'amr_mutations_PAS_Not_associated_with_R_(int.)',
                                                            'amr_mutations_PAS_Uncertain_significance',
                                                            'amr_mutations_PAS_Not_in_db.', 'amr_pheno_RBT',
                                                            'amr_mutations_RBT_Associated_with_R',
                                                            'amr_mutations_RBT_Associated_with_R_(int.)',
                                                            'amr_mutations_RBT_Not_associated_with_R',
                                                            'amr_mutations_RBT_Not_associated_with_R_(int.)',
                                                            'amr_mutations_RBT_Uncertain_significance',
                                                            'amr_mutations_RBT_Not_in_db.']
                records = {"isolate": outputtsvdict["sample"],
                           "pipeline_version": outputtsvdict["pipeline_version"],
                           "analysis_date": self._parse_date_to_iso(outputtsvdict["analysis_date"]),
                           # "downsampling": self._avro_input_commontsvoutput(outputtsvdict, "downsampling"), # downsampling was not yet reported in this mycobacterium pipeline version
                           "trimming": self._avro_input_commontsvoutput(outputtsvdict, "trimming"),
                           "assembly": self._avro_input_commontsvoutput(outputtsvdict, "assembly"),
                           "qc":
                               {"qc_fastqc": self._avro_input_commontsvoutput(outputtsvdict, "qc_fastqc"),
                               "qc_cgmlst": self._avro_input_commontsvoutput(outputtsvdict, "qc_cgmlst"),
                               "qc_reference": self._avro_input_commontsvoutput(outputtsvdict, "qc_reference"),
                               "qc_kraken": self._avro_input_commontsvoutput(outputtsvdict, "qc_kraken")
                                },
                           "kraken": self._avro_input_commontsvoutput(outputtsvdict, "kraken"),
                           "variant_calling": self._avro_input_commontsvoutput(outputtsvdict, "variant_calling"),
                           "variant_filtering": self._avro_input_commontsvoutput(outputtsvdict, "variant_filtering"),
                           "csb_rd": self._avro_input_commontsvoutput(outputtsvdict, "csb_rd"),
                           "51SNP": self._avro_input_commontsvoutput(outputtsvdict, "51SNP"),
                           "snpit": self._avro_input_commontsvoutput(outputtsvdict, "snpit"),
                           "spoligotyping": self._avro_input_commontsvoutput(outputtsvdict, "spoligotyping"),
                           "snp_lineage": self._avro_input_commontsvoutput(outputtsvdict, "snp_lineage"),
                           "amr_who": self._avro_input_commontsvoutput(outputtsvdict, "amr_who"),
                           "mlst": self._avro_input_typingschema(species, "mlst", "mlst", outputtsvdict),
                           "cgmlst": self._avro_input_typingschema(species, "cgmlst", "cgmlst", outputtsvdict),
                           "hits_ncbi_16s": outputtsvdict["hits_ncbi_16s"],
                           "hits_hsp65": outputtsvdict["hits_hsp65"],
                           "pointfinder_mutations": outputtsvdict["pointfinder_mutations"]
                           }

            elif species == "neisseria":
                self._common_output_arguments["serogroup"] = ['detected_serogroup', 'serogroup_nb_hits',
                                                              'serogroup_nb_hits_perfect', 'serogroup_total_loci']
                outputtsvdict['rplf-rplF'] = outputtsvdict["rplf-'rplF"].replace("'rplF", "rplF")
                records = {"isolate": outputtsvdict["sample"],
                           "pipeline_version": outputtsvdict["pipeline_version"],
                           "analysis_date": self._parse_date_to_iso(outputtsvdict["analysis_date"]),
                           "downsampling": self._avro_input_commontsvoutput(outputtsvdict, "downsampling"),
                           "trimming": self._avro_input_commontsvoutput(outputtsvdict, "trimming"),
                           "assembly": self._avro_input_commontsvoutput(outputtsvdict, "assembly"),
                           "qc":
                               {"qc_fastqc": self._avro_input_commontsvoutput(outputtsvdict, "qc_fastqc"),
                               "qc_cgmlst": self._avro_input_commontsvoutput(outputtsvdict, "qc_cgmlst"),
                               "qc_assembly": self._avro_input_commontsvoutput(outputtsvdict, "qc_assembly"),
                               "qc_kraken": self._avro_input_commontsvoutput(outputtsvdict, "qc_kraken")
                                },
                           "kraken": self._avro_input_commontsvoutput(outputtsvdict, "kraken"),
                           "serogroup": self._avro_input_commontsvoutput(outputtsvdict, "serogroup"),
                           "mlst": self._avro_input_typingschema(species, "mlst", "mlst", outputtsvdict),
                           "cgmlst": self._avro_input_typingschema(species, "cgmlst", "cgmlst", outputtsvdict),
                           "rplf": self._avro_input_typingschema(species, 'rplf', 'rplf', outputtsvdict),
                           "bast": self._avro_input_typingschema(species, 'bast', 'bast', outputtsvdict),
                           "pora": self._avro_input_typingschema(species, 'pora', 'pora', outputtsvdict),
                           "porb": self._avro_input_typingschema(species, 'porb', 'porb', outputtsvdict),
                           "feta": self._avro_input_typingschema(species, 'feta', 'feta', outputtsvdict),
                           "resistance_genes": self._avro_input_typingschema(species, 'resistance_genes',
                                                                             'resistance_genes', outputtsvdict),
                           "vaccine_targets": self._avro_input_typingschema(species, 'vaccine_targets',
                                                                            'vaccine_targets', outputtsvdict),
                           "fhbp": self._avro_input_typingschema(species, 'fhbp', 'fhbp', outputtsvdict),
                           "hits_ncbi_amr": outputtsvdict["hits_ncbi_amr"],
                           "hits_resfinder": outputtsvdict["hits_resfinder"]
                           }

            elif species == "stec":
                species = "ecoli"
                records = {"isolate": outputtsvdict["sample"],
                           "pipeline_version": outputtsvdict["pipeline_version"],
                           "analysis_date": self._parse_date_to_iso(outputtsvdict["analysis_date"]),
                           "downsampling": self._avro_input_commontsvoutput(outputtsvdict, "downsampling"),
                           "trimming": self._avro_input_commontsvoutput(outputtsvdict, "trimming"),
                           "assembly": self._avro_input_commontsvoutput(outputtsvdict, "assembly"),
                           "qc":
                               {"qc_fastqc": self._avro_input_commontsvoutput(outputtsvdict, "qc_fastqc"),
                               "qc_cgmlst": self._avro_input_commontsvoutput(outputtsvdict, "qc_cgmlst"),
                               "qc_assembly": self._avro_input_commontsvoutput(outputtsvdict, "qc_assembly"),
                               "qc_kraken": self._avro_input_commontsvoutput(outputtsvdict, "qc_kraken")
                                },
                           "kraken": self._avro_input_commontsvoutput(outputtsvdict, "kraken"),
                           "variant_calling": self._avro_input_commontsvoutput(outputtsvdict, "variant_calling"),
                           "variant_filtering": self._avro_input_commontsvoutput(outputtsvdict, "variant_filtering"),
                           "mlst_pasteur": self._avro_input_typingschema(species, "mlst_pasteur", "mlst-pasteur",
                                                                         outputtsvdict),
                           "mlst_warwick": self._avro_input_typingschema(species, "mlst_warwick", "mlst-warwick",
                                                                         outputtsvdict),
                           "cgmlst": self._avro_input_typingschema(species, "cgmlst", "cgmlst", outputtsvdict),
                           "hits_ncbi_amr": outputtsvdict["hits_ncbi_amr"],
                           "hits_resfinder": outputtsvdict["hits_resfinder"],
                           "hits_virulencefinder": outputtsvdict["hits_virulencefinder"],
                           "hits_virulencefinder_shiga": outputtsvdict["hits_virulencefinder_shiga"],
                           "hits_plasmidfinder": outputtsvdict["hits_plasmidfinder"],
                           "pointfinder_mutations": outputtsvdict["pointfinder_mutations"],
                           "hits_serotype_h": outputtsvdict["hits_serotype_h"],
                           "hits_serotype_o": outputtsvdict["hits_serotype_o"],
                           "serotype": outputtsvdict["serotype"]
                           }

            elif species == "salmonella":
                self._common_output_arguments["genotyphi"] = ['genotyphi_ESBLs_susceptibility',
                                                              'genotyphi_ESBLs_variants', 'genotyphi_ESBLs_genes',
                                                              'genotyphi_IncFIAHI1_susceptibility',
                                                              'genotyphi_IncFIAHI1_variants',
                                                              'genotyphi_IncFIAHI1_genes',
                                                              'genotyphi_IncHI1A_susceptibility',
                                                              'genotyphi_IncHI1A_variants', 'genotyphi_IncHI1A_genes',
                                                              'genotyphi_IncHI1BR27_susceptibility',
                                                              'genotyphi_IncHI1BR27_variants',
                                                              'genotyphi_IncHI1BR27_genes',
                                                              'genotyphi_IncY_susceptibility',
                                                              'genotyphi_IncY_variants', 'genotyphi_IncY_genes',
                                                              'genotyphi_aminoglycosides_susceptibility',
                                                              'genotyphi_aminoglycosides_variants',
                                                              'genotyphi_aminoglycosides_genes',
                                                              'genotyphi_azithromycin_susceptibility',
                                                              'genotyphi_azithromycin_variants',
                                                              'genotyphi_azithromycin_genes',
                                                              'genotyphi_beta-lactamases_susceptibility',
                                                              'genotyphi_beta-lactamases_variants',
                                                              'genotyphi_beta-lactamases_genes',
                                                              'genotyphi_macrolides_susceptibility',
                                                              'genotyphi_macrolides_variants',
                                                              'genotyphi_macrolides_genes',
                                                              'genotyphi_pST_susceptibility', 'genotyphi_pST_variants',
                                                              'genotyphi_pST_genes',
                                                              'genotyphi_phenicols_susceptibility',
                                                              'genotyphi_phenicols_variants',
                                                              'genotyphi_phenicols_genes',
                                                              'genotyphi_quinolones_susceptibility',
                                                              'genotyphi_quinolones_variants',
                                                              'genotyphi_quinolones_genes',
                                                              'genotyphi_sulfonamides_susceptibility',
                                                              'genotyphi_sulfonamides_variants',
                                                              'genotyphi_sulfonamides_genes',
                                                              'genotyphi_tetracyclines_susceptibility',
                                                              'genotyphi_tetracyclines_variants',
                                                              'genotyphi_tetracyclines_genes',
                                                              'genotyphi_trimethoprims_susceptibility',
                                                              'genotyphi_trimethoprims_variants',
                                                              'genotyphi_trimethoprims_genes',
                                                              'genotyphi_z66_susceptibility', 'genotyphi_z66_variants',
                                                              'genotyphi_z66_genes', 'genotyphi_phylo_group',
                                                              'genotyphi_species', 'genotyphi_lineage',
                                                              'genotyphi_phylo_group_per_covg',
                                                              'genotyphi_species_per_covg',
                                                              'genotyphi_lineage_per_covg',
                                                              'genotyphi_phylo_group_depth', 'genotyphi_species_depth',
                                                              'genotyphi_lineage_depth']
                # self._common_output_arguments["sistr"] = ['sistr_hits_serotype_h1_fliC', 'sistr_hits_serotype_h2_fljB',
                #                                           'sistr_hits_serotype_o_wzx', 'sistr_hits_serotype_o_wzy',
                #                                           'sistr_serotype_antigenic_formula',
                #                                           'sistr_serotype_serogroup', 'sistr_serotype_concensus']
                # self._common_output_arguments["seqsero2_kmer"] = ['seqsero2_kmer_O_antigen_prediction',
                #                                                   'seqsero2_kmer_H1_antigen_prediction(fliC)',
                #                                                   'seqsero2_kmer_H2_antigen_prediction(fljB)',
                #                                                   'seqsero2_kmer_Predicted_identification',
                #                                                   'seqsero2_kmer_Predicted_antigenic_profile',
                #                                                   'seqsero2_kmer_Predicted_serotype']
                # self._common_output_arguments["seqsero2_allele"] = ['seqsero2_allele_O_antigen_prediction',
                #                                                     'seqsero2_allele_H1_antigen_prediction(fliC)',
                #                                                     'seqsero2_allele_H2_antigen_prediction(fljB)',
                #                                                     'seqsero2_allele_Predicted_identification',
                #                                                     'seqsero2_allele_Predicted_antigenic_profile',
                #                                                     'seqsero2_allele_Predicted_serotype']
                # self._common_output_arguments["seqsero2_kmerread"] = ['seqsero2_kmerread_O_antigen_prediction',
                #                                                       'seqsero2_kmerread_H1_antigen_prediction(fliC)',
                #                                                       'seqsero2_kmerread_H2_antigen_prediction(fljB)',
                #                                                       'seqsero2_kmerread_Predicted_identification',
                #                                                       'seqsero2_kmerread_Predicted_antigenic_profile',
                #                                                       'seqsero2_kmerread_Predicted_serotype']
                records = {"isolate": outputtsvdict["sample"],
                           "pipeline_version": outputtsvdict["pipeline_version"],
                           "analysis_date": self._parse_date_to_iso(outputtsvdict["analysis_date"]),
                           "downsampling": self._avro_input_commontsvoutput(outputtsvdict, "downsampling"),
                           "trimming": self._avro_input_commontsvoutput(outputtsvdict, "trimming"),
                           "assembly": self._avro_input_commontsvoutput(outputtsvdict, "assembly"),
                           "qc":
                               {"qc_fastqc": self._avro_input_commontsvoutput(outputtsvdict, "qc_fastqc"),
                               "qc_cgmlst": self._avro_input_commontsvoutput(outputtsvdict, "qc_cgmlst"),
                               "qc_assembly": self._avro_input_commontsvoutput(outputtsvdict, "qc_assembly"),
                               "qc_kraken": self._avro_input_commontsvoutput(outputtsvdict, "qc_kraken")
                                },
                           "kraken": self._avro_input_commontsvoutput(outputtsvdict, "kraken"),
                           "variant_calling": self._avro_input_commontsvoutput(outputtsvdict, "variant_calling"),
                           "variant_filtering": self._avro_input_commontsvoutput(outputtsvdict, "variant_filtering"),
                           "mlst": self._avro_input_typingschema(species, "mlst", "mlst", outputtsvdict),
                           "cgmlst": self._avro_input_typingschema(species, "cgmlst", "cgmlst", outputtsvdict),
                           "genotyphi": self._avro_input_commontsvoutput(outputtsvdict, "genotyphi"),
                           # "sistr": self._avro_input_commontsvoutput(outputtsvdict, "sistr"),
                           # "seqsero2_kmer": self._avro_input_commontsvoutput(outputtsvdict, "seqsero2_kmer"),
                           # "seqsero2_allele": self._avro_input_commontsvoutput(outputtsvdict, "seqsero2_allele"),
                           # "seqsero2_kmerread": self._avro_input_commontsvoutput(outputtsvdict, "seqsero2_kmerread"),
                           "hits_ncbi_amr": outputtsvdict["hits_ncbi_amr"],
                           "hits_resfinder": outputtsvdict["hits_resfinder"],
                           "hits_plasmidfinder": outputtsvdict["hits_plasmidfinder"],
                           "pointfinder_mutations": outputtsvdict["pointfinder_mutations"],
                           "hits_vfdb_core": outputtsvdict["hits_vfdb_core"],
                           "spifinder_fastq": outputtsvdict["spifinder_fastq"],
                           "spifinder_fasta": outputtsvdict["spifinder_fasta"]
                           }

        else:
            logging.error(f"Species '{species}' not in supported species")
            raise RuntimeError(f"Species '{species}' not in supported species")

        return records

    def _avro_input_commontsvoutput(self, outputtsvdict: dict, commontsvoutputoption: str) -> dict:
        """
        :param outputtsvdict: The full outputdict
        :param commontsvoutputoption: string that is a key in self._common_output_arguments
        :return: a subset of the outputtsvdict in a dict with only 1 key, the commontsvoutputoption
        """
        common_tsv_output_dict = {}
        if commontsvoutputoption not in self._common_output_arguments.keys():
            logging.error(
                f"option {commontsvoutputoption} does not exist in tsv_output dictionary in this function in this script")
            raise RuntimeError(
                f"option {commontsvoutputoption} does not exist in tsv_output dictionary in this function in this script")
        else:
            common_tsv_output_dict[commontsvoutputoption] = {variable: outputtsvdict[variable] for variable in
                                                             self._common_output_arguments[commontsvoutputoption]}
        return common_tsv_output_dict[commontsvoutputoption]

    def _avro_input_typinglocus(self, locusname, outputtsvdict):
        """
        Creates a json string/dict to be used in a Mongo schema
        :param locusname: locusname as in tsv_output but with - replaced by _
        :param outputtsvdict: dict of output values separated by tab
        """
        avroschema_typinglocus_parsing = {"Locus": outputtsvdict[locusname.replace('.', '-')].split(",")[0],
                                          "Allele_designation": self._make_int_if_possible(
                                              outputtsvdict[locusname.replace('.', '-')].split(",")[1]),
                                          "Percentage_identity": float(
                                              outputtsvdict[locusname.replace('.', '-')].split(",")[2]) if
                                          outputtsvdict[locusname.replace('.', '-')].split(",")[2] != '-' else '-',
                                          "Coverage": outputtsvdict[locusname.replace('.', '-')].split(",")[3],
                                          "Type": outputtsvdict[locusname.replace('.', '-')].split(",")[4]
                                          }

        return avroschema_typinglocus_parsing

    def _avro_input_typingschema(self, species, schemename, schemedirname, outputtsvdict):
        # Scheme fields, keys here need to match tsv output
        scheme_fields = {}
        if schemename in ['mlst', 'mlst_warwick', 'mlst_pasteur']:
            scheme_fields[f"{schemename}-ST"] = self._make_int_if_possible(outputtsvdict[f"{schemename}-ST"])
            if species == 'listeria':
                scheme_fields["mlst-CC"] = outputtsvdict["mlst-CC"]
                scheme_fields["mlst-Lineage"] = outputtsvdict["mlst-Lineage"]
        elif schemename == 'pcr_serogroup':
            scheme_fields["pcr_serogroup-profile_id"] = self._make_int_if_possible(
                outputtsvdict["pcr_serogroup-profile_id"])
            scheme_fields["pcr_serogroup-serogroup"] = outputtsvdict["pcr_serogroup-serogroup"]
        elif schemename == 'rplf':
            scheme_fields["rplf-rplF_id"] = self._make_int_if_possible(outputtsvdict["rplf-rplF_id"])
            scheme_fields["rplf-genospecies"] = outputtsvdict["rplf-genospecies"]
        elif schemename == 'bast':
            scheme_fields["bast-BAST"] = self._make_int_if_possible(outputtsvdict["bast-BAST"])
            scheme_fields["bast-MenDeVAR_Bexsero_reactivity"] = outputtsvdict["bast-MenDeVAR_Bexsero_reactivity"]
            scheme_fields["bast-MenDeVAR_Trumenba_reactivity"] = outputtsvdict["bast-MenDeVAR_Trumenba_reactivity"]

        # Loci
        dirscheme = f"/db/sequence_typing/{species}/{schemedirname}"
        if os.path.isdir(dirscheme) is False:
            logging.error(f"scheme {schemedirname} was not found at {dirscheme}")
            raise RuntimeError(f"scheme {schemedirname} was not found at {dirscheme}")
        dirs = next(os.walk(dirscheme))[1]
        """
        this commented out part returns a dict like this: Scheme: {loci: {locusx: {pid: "pid", cov: "cov", ...} } } 
        whereas the new code below returns a list of locus dicts under loci rather than dicts of loci
        Keeping the code in case needed again later
        """
        # loci = {}
        # for dir in dirs:
        #     if not dir.startswith('.') and not (schemename == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (schemename == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
        #         loci["_".join([schemename, dir])] = self._avro_input_typinglocus(".".join([schemename, dir]), outputtsvdict)
        # locischeme = {}
        # locischeme["loci"] = loci
        # # Scheme
        # fields = {**scheme_fields, **locischeme}
        # return {key: value for key, value in fields.items()}
        loci = []
        for dir in dirs:
            if not dir.startswith('.') and not (
                    schemename == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (
                    schemename == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
                loci.append(self._avro_input_typinglocus(".".join([schemename, dir]), outputtsvdict))
        locischeme = {}
        locischeme["loci"] = loci

        # Scheme
        fields = {**scheme_fields, **locischeme}
        return {key: value for key, value in fields.items()}

    def _make_int_if_possible(self, value):
        """
        Converts (string) to int if possible
        Function is used because for e.g. allele designations or ST, the result can be - as well as int, and reading from tsv is always string.
        :param value: inputvalue(/string)
        """
        import re
        return int(value) if re.match('^[0-9]+$', value) else value
