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
        if str(species) in self._species_options:
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
                        self._make_avroschema_typingscheme('listeria', 'mlst', 'mlst'),
                        self._make_avroschema_typingscheme('listeria', 'cgmlst', 'cgmlst'),
                        self._make_avroschema_typingscheme('listeria', 'pcr_serogroup', 'serogroup'),
                        self._make_avroschema_typingscheme('listeria', 'typing_virulence', 'virulence'),
                        self._make_avroschema_typingscheme('listeria', 'typing_amr', 'antibiotic_resistance'),
                        self._make_avroschema_typingscheme('listeria', 'species_confirmation', 'species_confirmation'),
                        self._make_avroschema_typingscheme('listeria', 'metal_detergent', 'metal_detergent_resistance'),
                        {"name": "hits_argannot", "type": "string"},
                        {"name": "hits_card", "type": "string"},
                        {"name": "hits_ncbi_amr", "type": "string"},
                        {"name": "hits_resfinder", "type": "string"},
                        {"name": "hits_virulencefinder", "type": "string"},
                        {"name": "hits_plasmidfinder", "type": "string"}
                               ]
                                   }
            elif species == "mycobacterium":
                schema = {}
            elif species == "neisseria":
                schema = {}
            elif species == "stec":
                schema = {}
            elif species == "salmonella":
                schema = {}

        else:
            logging.error(f"Species '{species}' not in supported species")

        return schema

    def _make_avroschema_commontsvoutput(self, commontsvoutputoption):
        common_tsv_output_schema = {}
        if commontsvoutputoption not in self._common_output_arguments.keys():
            logging.error("option does not exist in tsv_output dictionary in this function in this script")
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