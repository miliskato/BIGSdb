import os
import logging
from .avro_superclass import Avro_superclass

class Avroschema(Avro_superclass):
    """
    Class for creating Avro Schemas
    """
    def __init__(self):
        Avro_superclass.__init__(self)
        logging.info("Avroschema initialised")

    def create_schema(self, species: str):
        return self._schema_selection(species)

    def _schema_selection(self, species):
        schema = {}
        species = str(species)
        if species in self._species_options:
            logging.info(f"species {species} in allowed species")
            if species == "listeria":
                schema = {
                    "name": "sample",
                    "type": "record",
                    "fields": [
                        {"name": "isolate", "type": "string"},
                        {"name": "pipeline_version", "type": "float"},
                        self._make_avroschema_commontsvoutput("downsampling"),
                        self._make_avroschema_commontsvoutput("trimming"),
                        self._make_avroschema_commontsvoutput("assembly"),
                        self._make_avroschema_commontsvoutput("qc_fastqc"),
                        self._make_avroschema_commontsvoutput("qc_cgmlst"),
                        self._make_avroschema_commontsvoutput("qc_assembly"),
                        self._make_avroschema_commontsvoutput("qc_kraken"),
                        self._make_avroschema_commontsvoutput("kraken"),
                        self._make_avroschema_typingscheme(species, 'mlst', 'mlst'),
                        self._make_avroschema_typingscheme(species, 'cgmlst', 'cgmlst'),
                        self._make_avroschema_typingscheme(species, 'pcr_serogroup', 'serogroup'),
                        self._make_avroschema_typingscheme(species, 'typing_virulence', 'virulence'),
                        self._make_avroschema_typingscheme(species, 'typing_amr', 'antibiotic_resistance'),
                        self._make_avroschema_typingscheme(species, 'species_confirmation', 'species_confirmation'),
                        self._make_avroschema_typingscheme(species, 'metal_detergent', 'metal_detergent_resistance'),
                        {"name": "hits_ncbi_amr", "type": "string"},
                        {"name": "hits_resfinder", "type": "string"},
                        {"name": "hits_virulencefinder", "type": "string"},
                        {"name": "hits_plasmidfinder", "type": "string"}
                               ]
                                   }
            elif species == "mycobacterium":
                self._common_output_arguments["csb_rd"] = ['csb_detected', 'RD1_detected', 'RD9_detected']
                self._common_output_arguments["51SNP"] = ['51SNP-positive_control', '51SNP-gyrB_group', '51SNP-genetic_group', '51SNP-scg', '51SNP-st', '51SNP-matching_snps', '51SNP-SNP01', '51SNP-SNP02', '51SNP-SNP03', '51SNP-SNP04', '51SNP-SNP05', '51SNP-SNP06', '51SNP-SNP07', '51SNP-SNP08', '51SNP-SNP09', '51SNP-SNP10', '51SNP-SNP11', '51SNP-SNP12', '51SNP-SNP13', '51SNP-SNP14', '51SNP-SNP15', '51SNP-SNP16', '51SNP-SNP17', '51SNP-SNP18', '51SNP-SNP19', '51SNP-SNP20', '51SNP-SNP21', '51SNP-SNP22', '51SNP-SNP23', '51SNP-SNP24', '51SNP-SNP25', '51SNP-SNP26', '51SNP-SNP27', '51SNP-SNP28', '51SNP-SNP29', '51SNP-SNP30', '51SNP-SNP31', '51SNP-SNP32', '51SNP-SNP33', '51SNP-SNP34', '51SNP-SNP35', '51SNP-SNP36', '51SNP-SNP37', '51SNP-SNP38', '51SNP-SNP39', '51SNP-SNP40', '51SNP-SNP41', '51SNP-SNP42', '51SNP-SNP43', '51SNP-SNP44', '51SNP-SNP45', '51SNP-SNP46', '51SNP-SNP47', '51SNP-SNP48', '51SNP-SNP49', '51SNP-SNP50', '51SNP-SNP51']
                self._common_output_arguments["snpit"] = ['snpit_species', 'snpit_lineage', 'snpit_sublineage', 'snpit_percent_matched']
                self._common_output_arguments["spoligotyping"] = ['spoligotype_binary', 'spoligotype_octal', 'sit_number']
                self._common_output_arguments["snp_lineage"] = ['snp_lineages']
                self._common_output_arguments["amr_who"] = ['amr_type', 'amr_first_line_resistant', 'amr_second_line_group_a_resistant', 'amr_second_line_group_b_resistant', 'amr_pheno_INH', 'amr_mutations_INH_Associated_with_R', 'amr_mutations_INH_Associated_with_R_(int.)', 'amr_mutations_INH_Not_associated_with_R', 'amr_mutations_INH_Not_associated_with_R_(int.)', 'amr_mutations_INH_Uncertain_significance', 'amr_mutations_INH_Not_in_db.', 'amr_pheno_RIF', 'amr_mutations_RIF_Associated_with_R', 'amr_mutations_RIF_Associated_with_R_(int.)', 'amr_mutations_RIF_Not_associated_with_R', 'amr_mutations_RIF_Not_associated_with_R_(int.)', 'amr_mutations_RIF_Uncertain_significance', 'amr_mutations_RIF_Not_in_db.', 'amr_pheno_LEV', 'amr_mutations_LEV_Associated_with_R', 'amr_mutations_LEV_Associated_with_R_(int.)', 'amr_mutations_LEV_Not_associated_with_R', 'amr_mutations_LEV_Not_associated_with_R_(int.)', 'amr_mutations_LEV_Uncertain_significance', 'amr_mutations_LEV_Not_in_db.', 'amr_pheno_MXF', 'amr_mutations_MXF_Associated_with_R', 'amr_mutations_MXF_Associated_with_R_(int.)', 'amr_mutations_MXF_Not_associated_with_R', 'amr_mutations_MXF_Not_associated_with_R_(int.)', 'amr_mutations_MXF_Uncertain_significance', 'amr_mutations_MXF_Not_in_db.', 'amr_pheno_AMI', 'amr_mutations_AMI_Associated_with_R', 'amr_mutations_AMI_Associated_with_R_(int.)', 'amr_mutations_AMI_Not_associated_with_R', 'amr_mutations_AMI_Not_associated_with_R_(int.)', 'amr_mutations_AMI_Uncertain_significance', 'amr_mutations_AMI_Not_in_db.', 'amr_pheno_CAP', 'amr_mutations_CAP_Associated_with_R', 'amr_mutations_CAP_Associated_with_R_(int.)', 'amr_mutations_CAP_Not_associated_with_R', 'amr_mutations_CAP_Not_associated_with_R_(int.)', 'amr_mutations_CAP_Uncertain_significance', 'amr_mutations_CAP_Not_in_db.', 'amr_pheno_KAN', 'amr_mutations_KAN_Associated_with_R', 'amr_mutations_KAN_Associated_with_R_(int.)', 'amr_mutations_KAN_Not_associated_with_R', 'amr_mutations_KAN_Not_associated_with_R_(int.)', 'amr_mutations_KAN_Uncertain_significance', 'amr_mutations_KAN_Not_in_db.', 'amr_pheno_STM', 'amr_mutations_STM_Associated_with_R', 'amr_mutations_STM_Associated_with_R_(int.)', 'amr_mutations_STM_Not_associated_with_R', 'amr_mutations_STM_Not_associated_with_R_(int.)', 'amr_mutations_STM_Uncertain_significance', 'amr_mutations_STM_Not_in_db.', 'amr_pheno_ETH', 'amr_mutations_ETH_Associated_with_R', 'amr_mutations_ETH_Associated_with_R_(int.)', 'amr_mutations_ETH_Not_associated_with_R', 'amr_mutations_ETH_Not_associated_with_R_(int.)', 'amr_mutations_ETH_Uncertain_significance', 'amr_mutations_ETH_Not_in_db.', 'amr_pheno_PZA', 'amr_mutations_PZA_Associated_with_R', 'amr_mutations_PZA_Associated_with_R_(int.)', 'amr_mutations_PZA_Not_associated_with_R', 'amr_mutations_PZA_Not_associated_with_R_(int.)', 'amr_mutations_PZA_Uncertain_significance', 'amr_mutations_PZA_Not_in_db.', 'amr_pheno_BDQ', 'amr_mutations_BDQ_Associated_with_R', 'amr_mutations_BDQ_Associated_with_R_(int.)', 'amr_mutations_BDQ_Not_associated_with_R', 'amr_mutations_BDQ_Not_associated_with_R_(int.)', 'amr_mutations_BDQ_Uncertain_significance', 'amr_mutations_BDQ_Not_in_db.', 'amr_pheno_CFZ', 'amr_mutations_CFZ_Associated_with_R', 'amr_mutations_CFZ_Associated_with_R_(int.)', 'amr_mutations_CFZ_Not_associated_with_R', 'amr_mutations_CFZ_Not_associated_with_R_(int.)', 'amr_mutations_CFZ_Uncertain_significance', 'amr_mutations_CFZ_Not_in_db.', 'amr_pheno_DLM', 'amr_mutations_DLM_Associated_with_R', 'amr_mutations_DLM_Associated_with_R_(int.)', 'amr_mutations_DLM_Not_associated_with_R', 'amr_mutations_DLM_Not_associated_with_R_(int.)', 'amr_mutations_DLM_Uncertain_significance', 'amr_mutations_DLM_Not_in_db.', 'amr_pheno_EMB', 'amr_mutations_EMB_Associated_with_R', 'amr_mutations_EMB_Associated_with_R_(int.)', 'amr_mutations_EMB_Not_associated_with_R', 'amr_mutations_EMB_Not_associated_with_R_(int.)', 'amr_mutations_EMB_Uncertain_significance', 'amr_mutations_EMB_Not_in_db.', 'amr_pheno_LZD', 'amr_mutations_LZD_Associated_with_R', 'amr_mutations_LZD_Associated_with_R_(int.)', 'amr_mutations_LZD_Not_associated_with_R', 'amr_mutations_LZD_Not_associated_with_R_(int.)', 'amr_mutations_LZD_Uncertain_significance', 'amr_mutations_LZD_Not_in_db.', 'amr_pheno_DCS', 'amr_mutations_DCS_Associated_with_R', 'amr_mutations_DCS_Associated_with_R_(int.)', 'amr_mutations_DCS_Not_associated_with_R', 'amr_mutations_DCS_Not_associated_with_R_(int.)', 'amr_mutations_DCS_Uncertain_significance', 'amr_mutations_DCS_Not_in_db.', 'amr_pheno_EFF', 'amr_mutations_EFF_Associated_with_R', 'amr_mutations_EFF_Associated_with_R_(int.)', 'amr_mutations_EFF_Not_associated_with_R', 'amr_mutations_EFF_Not_associated_with_R_(int.)', 'amr_mutations_EFF_Uncertain_significance', 'amr_mutations_EFF_Not_in_db.', 'amr_pheno_PAS', 'amr_mutations_PAS_Associated_with_R', 'amr_mutations_PAS_Associated_with_R_(int.)', 'amr_mutations_PAS_Not_associated_with_R', 'amr_mutations_PAS_Not_associated_with_R_(int.)', 'amr_mutations_PAS_Uncertain_significance', 'amr_mutations_PAS_Not_in_db.', 'amr_pheno_RBT', 'amr_mutations_RBT_Associated_with_R', 'amr_mutations_RBT_Associated_with_R_(int.)', 'amr_mutations_RBT_Not_associated_with_R', 'amr_mutations_RBT_Not_associated_with_R_(int.)', 'amr_mutations_RBT_Uncertain_significance', 'amr_mutations_RBT_Not_in_db.']
                schema = {
                    "name": "sample",
                    "type": "record",
                    "fields": [
                        {"name": "isolate", "type": "string"},
                        {"name": "pipeline_version", "type": "float"},
                        self._make_avroschema_commontsvoutput("downsampling"),
                        self._make_avroschema_commontsvoutput("trimming"),
                        self._make_avroschema_commontsvoutput("assembly"),
                        self._make_avroschema_commontsvoutput("qc_fastqc"),
                        self._make_avroschema_commontsvoutput("qc_cgmlst"),
                        self._make_avroschema_commontsvoutput("qc_reference"),
                        self._make_avroschema_commontsvoutput("qc_kraken"),
                        self._make_avroschema_commontsvoutput("kraken"),
                        self._make_avroschema_commontsvoutput("variant_calling"),
                        self._make_avroschema_commontsvoutput("variant_filtering"),
                        self._make_avroschema_commontsvoutput("csb_rd"),
                        self._make_avroschema_commontsvoutput("51SNP"),
                        self._make_avroschema_commontsvoutput("snpit"),
                        self._make_avroschema_commontsvoutput("spoligotyping"),
                        self._make_avroschema_commontsvoutput("snp_lineage"),
                        self._make_avroschema_commontsvoutput("amr_who"),
                        self._make_avroschema_typingscheme(species, 'mlst', 'mlst'),
                        self._make_avroschema_typingscheme(species, 'cgmlst', 'cgmlst'),
                        {"name": "hits_ncbi_16s", "type": "string"},
                        {"name": "hits_hsp65", "type": "string"},
                        {"name": "pointfinder_mutations", "type": "string"}
                    ]
                }
            elif species == "neisseria":
                self._common_output_arguments["serogroup"] = ['detected_serogroup', 'serogroup_nb_hits', 'serogroup_nb_hits_perfect', 'serogroup_total_loci']
                schema = {
                    "name": "sample",
                    "type": "record",
                    "fields": [
                        {"name": "isolate", "type": "string"},
                        {"name": "pipeline_version", "type": "float"},
                        self._make_avroschema_commontsvoutput("downsampling"),
                        self._make_avroschema_commontsvoutput("trimming"),
                        self._make_avroschema_commontsvoutput("assembly"),
                        self._make_avroschema_commontsvoutput("qc_fastqc"),
                        self._make_avroschema_commontsvoutput("qc_cgmlst"),
                        self._make_avroschema_commontsvoutput("qc_assembly"),
                        self._make_avroschema_commontsvoutput("qc_kraken"),
                        self._make_avroschema_commontsvoutput("kraken"),
                        self._make_avroschema_typingscheme(species, 'mlst', 'mlst'),
                        self._make_avroschema_typingscheme(species, 'cgmlst', 'cgmlst'),
                        self._make_avroschema_typingscheme(species, 'rplf', 'rplf'),
                        self._make_avroschema_typingscheme(species, 'bast', 'bast'),
                        self._make_avroschema_typingscheme(species, 'pora', 'pora'),
                        self._make_avroschema_typingscheme(species, 'porb', 'porb'),
                        self._make_avroschema_typingscheme(species, 'feta', 'feta'),
                        self._make_avroschema_typingscheme(species, 'resistance_genes', 'resistance_genes'),
                        self._make_avroschema_typingscheme(species, 'vaccine_targets', 'vaccine_targets'),
                        self._make_avroschema_typingscheme(species, 'fhbp', 'fhbp'),
                        {"name": "hits_ncbi_amr", "type": "string"},
                        {"name": "hits_resfinder", "type": "string"},
                    ]
                }
            elif species == "stec":
                schema = {}
            elif species == "salmonella":
                schema = {}

        else:
            logging.error(f"Species '{species}' not in supported species")
            raise RuntimeError(f"Species '{species}' not in supported species")

        return schema

    def _make_avroschema_commontsvoutput(self, commontsvoutputoption):
        common_tsv_output_schema = {}
        if commontsvoutputoption not in self._common_output_arguments.keys():
            logging.error(f"option {commontsvoutputoption} does not exist in tsv_output dictionary in this function in this script")
            raise RuntimeError(f"option {commontsvoutputoption} does not exist in tsv_output dictionary in this function in this script")
        else:
            common_tsv_output_schema = {"name": commontsvoutputoption,
                                                 "type": {"name": "_".join([commontsvoutputoption,"inner"]),
                                                          "type": "record",
                                                          "fields": [{"name": x,
                                                                      "type": "string"} for x in self._common_output_arguments[commontsvoutputoption]
                                                                     ]
                                                          }

                                         }
        return common_tsv_output_schema

    def _make_avroschema_typinglocus(self, locusname):
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

    def _make_avroschema_typingscheme(self, species, schemename, schemedirname):
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
            scheme_fields["rplF_id"] = {"name": "rplf-rplF_id", "type": ["int", "string"]}
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
            raise RuntimeError(f"scheme {schemedirname} was not found at {dirscheme}")
        dirs = next(os.walk(dirscheme))[1]
        for dir in dirs:
            # todo  check schemename below with these special neisseria schemes
            if not dir.startswith('.') and not (schemename == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (schemename == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
                loci[dir] = self._make_avroschema_typinglocus("_".join([schemename, dir]))

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