import os
import logging

def make_int_if_possible(value):
    """
    Converts (string) to int if possible
    Function is used because for e.g. allele designations or ST, the result can be - as well as int, and reading from tsv is always string.
    :param value: inputvalue(/string)
    """
    import re
    return int(value) if re.match('^[0-9]+$', value) else value

def avro_input_commontsvoutput(listofoptions):
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

def avro_input_typinglocus(locusname, outputtsvdict):
    """
    Creates a json string/dict to be used in an Avro schema
    :param locusname: locusname as in tsv_output but with - replaced by _
    :param outputtsvdict: dict of output values separated by tab
    """
    avroschema_typinglocus_parsing = {"Locus": outputtsvdict[locusname.replace('.', '-')].split(",")[0],
                                      "Allele_designation": make_int_if_possible(outputtsvdict[locusname.replace('.', '-')].split(",")[1]),
                                      "Percentage_identity": float(outputtsvdict[locusname.replace('.', '-')].split(",")[2]) if outputtsvdict[locusname.replace('.', '-')].split(",")[2] != '-' else '-',
                                      "Coverage": outputtsvdict[locusname.replace('.', '-')].split(",")[3],
                                      "Type": outputtsvdict[locusname.replace('.', '-')].split(",")[4]
                                      }

    return avroschema_typinglocus_parsing

def avro_input_typingschema(species, schemename, schemedirname, outputtsvdict):
    # Scheme fields, keys here need to match tsv output
    scheme_fields = {}
    if schemename in ['mlst', 'mlst_warwick', 'mlst_pasteur']:
        scheme_fields["mlst-ST"] = make_int_if_possible(outputtsvdict["mlst-ST"])
        if species == 'listeria':
            scheme_fields["mlst-CC"] = outputtsvdict["mlst-CC"]
            scheme_fields["mlst-Lineage"] = outputtsvdict["mlst-Lineage"]
    elif schemename == 'pcr_serogroup':
        scheme_fields["pcr_serogroup-profile_id"] = make_int_if_possible(outputtsvdict["pcr_serogroup-profile_id"])
        scheme_fields["pcr_serogroup-serogroup"] = outputtsvdict["pcr_serogroup-serogroup"]
    elif schemename == 'rplf':
        scheme_fields["rplf-rplF-id"] = {"name": "rplf-rplF-id", "type": ["int", "string"]}
        scheme_fields["rplf-genospecies"] = {"name": "rplf-genospecies", "type": "string"}
    elif schemename == 'bast':
        scheme_fields["bast-BAST"] = {"name": "bast-BAST", "type": ["int", "string"]}
        scheme_fields["bast-MenDeVAR_Bexsero_reactivity"] = {"name": "bast-MenDeVAR_Bexsero_reactivity", "type": "string"}
        scheme_fields["bast-MenDeVAR_Trumenba_reactivity"] = {"name": "bast-MenDeVAR_Trumenba_reactivity", "type": "string"}

    # Loci
    loci = {}
    dirscheme = f"/db/sequence_typing/{species}/{schemedirname}"
    if os.path.isdir(dirscheme) is False:
        logging.error(f"scheme {schemedirname} was not found at {dirscheme}")
    dirs = next(os.walk(dirscheme))[1]
    for dir in dirs:
        # todo  check schemename below with these special neisseria schemes
        if not dir.startswith('.') and not (schemename == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (schemename == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
            loci["_".join([schemename, dir])] = avro_input_typinglocus(".".join([schemename, dir]), outputtsvdict)

    # Scheme
    fields = {**scheme_fields, **loci}
    return {key: value for key, value in fields.items()}
