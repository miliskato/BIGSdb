import os
import logging

def make_avroschema_commontsvoutput(listofoptions):
    common_tsv_output = {}
    tsv_output_dict = {"downsampling": ['downsampling_coverage_estimated', 'downsampling_coverage_target', 'downsampling_downsample_factor', 'downsampling_mean_read_length', 'downsampling_nb_read_pairs_in', 'downsampling_nb_read_pairs_out', 'downsampling_size_ref_genome', 'downsampling_total_bases'],
                       "trimming": ['trimming_pairs_in', 'trimming_pairs_out', 'trimming_fwd_only_surviving', 'trimming_rev_only_surviving', 'trimming_pairs_both_dropped'],
                       "assembly": ['assembly_n50', 'assembly_nb_contigs', 'assembly_total_length'],
                       "qc_fastqc": ['qc_fqc_avg_qual_fwd_status', 'qc_fqc_avg_qual_fwd_value', 'qc_fqc_avg_qual_rev_status', 'qc_fqc_avg_qual_rev_value', 'qc_fqc_gc_fwd_status', 'qc_fqc_gc_fwd_value', 'qc_fqc_gc_rev_status', 'qc_fqc_gc_rev_value', 'qc_fqc_n_fraction_fwd_status', 'qc_fqc_n_fraction_fwd_value', 'qc_fqc_n_fraction_rev_status', 'qc_fqc_n_fraction_rev_value', 'qc_fqc_per_base_fwd_status', 'qc_fqc_per_base_fwd_value', 'qc_fqc_per_base_rev_status', 'qc_fqc_per_base_rev_value', 'qc_fqc_qscore_fwd_status', 'qc_fqc_qscore_fwd_value', 'qc_fqc_qscore_rev_status', 'qc_fqc_qscore_rev_value', 'qc_fqc_seq_len_fwd_status', 'qc_fqc_seq_len_fwd_value', 'qc_fqc_seq_len_rev_status', 'qc_fqc_seq_len_rev_value'],
                       "qc_cgmlst": ['qc_cgmlst_status', 'qc_cgmlst_value'],
                       "qc_assembly": ['qc_cov_assembly_status', 'qc_cov_assembly_value', 'qc_map_rate_assembly_status', 'qc_map_rate_assembly_value'],
                       "qc_kraken": ['qc_kraken_status', 'qc_kraken_value'],
                       "kraken": ['kraken2_expected_species', 'kraken2_expected_species_occurence', 'kraken2_contaminants_warn', 'kraken2_contaminants_fail']
                       }
    for option in listofoptions:
        if option not in listofoptions:
            logging.error("option does not exist in tsv_output dictionary in this function in this script")
        else:
            common_tsv_output[option] = {"name": option,
                                                 "type": {"name": "_".join([option,"inner"]),
                                                          "type": "record",
                                                          "fields": [{"name": x,
                                                                      "type": "string"} for x in tsv_output_dict[option]
                                                                     ]
                                                          }
                                                 }
    return common_tsv_output

def make_avroschema_typinglocus(locusname):
    """
    Creates a json string/dict to be used in an Avro schema
    :param locusname: locusname as in tsv_output but with - replaced by _
    """
    avroschema_typinglocus = {"name": locusname,
                                 "type": {"name": "_".join([locusname,"inner"]),
                                          "type": "record",
                                          "fields": [{"name": "Locus",
                                                      "type": "string"},
                                                     {"name": "Allele_designation",
                                                      "type": ["int", "string"]},
                                                     {"name": "Percentage_identity",
                                                      "type": ["float", "string"]},
                                                     {"name": "Coverage",
                                                      "type": "string"},
                                                     {"name": "Type",
                                                      "type": "string"}
                                                     ]
                                          }
                                 }
    return avroschema_typinglocus

def make_avroschema_typingscheme(species, schemename, schemedirname):
    # Scheme fields, keys here do not matter
    scheme_fields = {}
    if schemename in ['mlst', 'mlst_warwick', 'mlst_pasteur']:
        scheme_fields["ST"] = {"name": "mlst-ST", "type": ["int", "string"]}
        if species == 'listeria':
            scheme_fields["CC"] = {"name": "mlst-CC", "type": "string"}
            scheme_fields["Lineage"] = {"name": "mlst-Lineage", "type": "string"}
    elif schemename == 'pcr_serogroup':
        scheme_fields["profile_id"] = {"name": "pcr_serogroup-profile_id", "type": ["int", "string"]}
        scheme_fields["serogroup"] = {"name": "pcr_serogroup-serogroup", "type": "string"}
    elif schemename == 'rplf':
        scheme_fields["rplF_id"] = {"name": "rplf-rplF-id", "type": ["int", "string"]}
        scheme_fields["genospecies"] = {"name": "rplf-genospecies", "type": "string"}
    elif schemename == 'bast':
        scheme_fields["bast"] = {"name": "bast-BAST", "type": ["int", "string"]}
        scheme_fields["MenDeVAR_Bexsero_reactivity"] = {"name": "bast-MenDeVAR_Bexsero_reactivity", "type": "string"}
        scheme_fields["MenDeVAR_Trumenba_reactivity"] = {"name": "bast-MenDeVAR_Trumenba_reactivity", "type": "string"}

    # Loci
    loci = {}
    dirscheme = f"/db/sequence_typing/{species}/{schemedirname}"
    if os.path.isdir(dirscheme) is False:
        logging.error(f"scheme {schemedirname} was not found at {dirscheme}")
    dirs = next(os.walk(dirscheme))[1]
    for dir in dirs:
        # todo  check schemename below with these special neisseria schemes
        if not dir.startswith('.') and not (schemename == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (schemename == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
            loci[dir] = make_avroschema_typinglocus("_".join([schemename, dir]))


    # Scheme
    fields = {**scheme_fields, **loci}
    typingscheme = {
            "name": schemename,
            "type": {
                        "type": "record",
                        "name": "_".join(["inner_record", schemename]),
                        "fields": [value for key, value in fields.items()
                                   ]
                         }
                 }
    return typingscheme