import os
import logging
from .avro_superclass import Avro_superclass

class Avrowriting(Avro_superclass):
    """
    Class for creating Avro Schemas
    """
    def __init__(self):
        Avro_superclass.__init__(self)
        logging.info("Avroswriting initialised")

    def parse_output(self, species: str, outputtsvdict : dict):
        return self._species_selection(species, outputtsvdict)

    def _species_selection(self, species, outputtsvdict):
        records = []
        species = str(species)
        if species in self._species_options:
            logging.info(f"species {species} in allowed species")
            if species == "listeria":
                # records needs to be a list for fastavro (even though only one sample at a time in our case)
                records = [{"isolate": outputtsvdict["sample"],
                            "pipeline_version": float(outputtsvdict["pipeline_version"]),
                            "downsampling": self._avro_input_commontsvoutput(outputtsvdict, "downsampling"),
                            "trimming": self._avro_input_commontsvoutput(outputtsvdict, "trimming"),
                            "assembly": self._avro_input_commontsvoutput(outputtsvdict, "assembly"),
                            "qc_fastqc": self._avro_input_commontsvoutput(outputtsvdict, "qc_fastqc"),
                            "qc_cgmlst": self._avro_input_commontsvoutput(outputtsvdict, "qc_cgmlst"),
                            "qc_assembly": self._avro_input_commontsvoutput(outputtsvdict, "qc_assembly"),
                            "qc_kraken": self._avro_input_commontsvoutput(outputtsvdict, "qc_kraken"),
                            "kraken": self._avro_input_commontsvoutput(outputtsvdict, "kraken"),
                            "mlst": self._avro_input_typingschema("listeria", "mlst", "mlst", outputtsvdict),
                            "cgmlst": self._avro_input_typingschema("listeria", "cgmlst", "cgmlst", outputtsvdict),
                            "pcr_serogroup": self._avro_input_typingschema("listeria", "pcr_serogroup", "serogroup", outputtsvdict),
                            'typing_virulence': self._avro_input_typingschema('listeria', 'typing_virulence', 'virulence', outputtsvdict),
                            'typing_amr': self._avro_input_typingschema('listeria', 'typing_amr', 'antibiotic_resistance', outputtsvdict),
                            'species_confirmation': self._avro_input_typingschema('listeria', 'species_confirmation',
                                                              'species_confirmation', outputtsvdict),
                            'metal_detergent': self._avro_input_typingschema('listeria', 'metal_detergent',
                                                              'metal_detergent_resistance', outputtsvdict),
                            "hits_argannot": outputtsvdict["hits_argannot"],
                            "hits_card": outputtsvdict["hits_card"],
                            "hits_ncbi_amr": outputtsvdict["hits_ncbi_amr"],
                            "hits_resfinder": outputtsvdict["hits_resfinder"],
                            "hits_virulencefinder": outputtsvdict["hits_virulencefinder"],
                            "hits_plasmidfinder": outputtsvdict["hits_plasmidfinder"]
                            }
                           ]
            elif species == "mycobacterium":
                pass # todo
            elif species == "neisseria":
                pass # todo
            elif species == "stec":
                pass # todo
            elif species == "salmonella":
                pass # todo
        else:
            logging.error(f"Species '{species}' not in supported species")

        return records


    def _avro_input_commontsvoutput(self, outputtsvdict, commontsvoutputoption : str):
        common_tsv_output_dict = {}
        if commontsvoutputoption not in self._common_output_arguments.keys():
            logging.error("option does not exist in tsv_output dictionary in this function in this script")
        else:
            common_tsv_output_dict[commontsvoutputoption] = {variable: outputtsvdict[variable] for variable in self._common_output_arguments[commontsvoutputoption]}
        return common_tsv_output_dict[commontsvoutputoption]

    def _avro_input_typinglocus(self, locusname, outputtsvdict):
        """
        Creates a json string/dict to be used in an Avro schema
        :param locusname: locusname as in tsv_output but with - replaced by _
        :param outputtsvdict: dict of output values separated by tab
        """
        avroschema_typinglocus_parsing = {"Locus": outputtsvdict[locusname.replace('.', '-')].split(",")[0],
                                          "Allele_designation": self._make_int_if_possible(outputtsvdict[locusname.replace('.', '-')].split(",")[1]),
                                          "Percentage_identity": float(outputtsvdict[locusname.replace('.', '-')].split(",")[2]) if outputtsvdict[locusname.replace('.', '-')].split(",")[2] != '-' else '-',
                                          "Coverage": outputtsvdict[locusname.replace('.', '-')].split(",")[3],
                                          "Type": outputtsvdict[locusname.replace('.', '-')].split(",")[4]
                                          }

        return avroschema_typinglocus_parsing

    def _avro_input_typingschema(self, species, schemename, schemedirname, outputtsvdict):
        # Scheme fields, keys here need to match tsv output
        scheme_fields = {}
        if schemename in ['mlst', 'mlst_warwick', 'mlst_pasteur']:
            scheme_fields["mlst-ST"] = self._make_int_if_possible(outputtsvdict["mlst-ST"])
            if species == 'listeria':
                scheme_fields["mlst-CC"] = outputtsvdict["mlst-CC"]
                scheme_fields["mlst-Lineage"] = outputtsvdict["mlst-Lineage"]
        elif schemename == 'pcr_serogroup':
            scheme_fields["pcr_serogroup-profile_id"] = self._make_int_if_possible(outputtsvdict["pcr_serogroup-profile_id"])
            scheme_fields["pcr_serogroup-serogroup"] = outputtsvdict["pcr_serogroup-serogroup"]
        elif schemename == 'rplf':
            scheme_fields["rplf-rplF-id"] = self._make_int_if_possible(outputtsvdict["rplf-rplF-id"])
            scheme_fields["rplf-genospecies"] = outputtsvdict["rplf-genospecies"]
        elif schemename == 'bast':
            scheme_fields["bast-BAST"] = self._make_int_if_possible(outputtsvdict["bast-BAST"])
            scheme_fields["bast-MenDeVAR_Bexsero_reactivity"] = outputtsvdict["bast-MenDeVAR_Bexsero_reactivity"]
            scheme_fields["bast-MenDeVAR_Trumenba_reactivity"] = outputtsvdict["bast-MenDeVAR_Trumenba_reactivity"]

        # Loci
        loci = {}
        dirscheme = f"/db/sequence_typing/{species}/{schemedirname}"
        if os.path.isdir(dirscheme) is False:
            logging.error(f"scheme {schemedirname} was not found at {dirscheme}")
        dirs = next(os.walk(dirscheme))[1]
        for dir in dirs:
            # todo  check schemename below with these special neisseria schemes
            if not dir.startswith('.') and not (schemename == 'fHbp_nucl' and (dir != 'fHbp_allele' and dir != 'fHbp_DNAfrag_Pasteur')) and not (schemename == 'fHbp_pept' and (dir == 'fHbp_allele' or dir == 'fHbp_DNAfrag_Pasteur')):
                loci["_".join([schemename, dir])] = self._avro_input_typinglocus(".".join([schemename, dir]), outputtsvdict)

        # Scheme
        fields = {**scheme_fields, **loci}
        return {key: value for key, value in fields.items()}
