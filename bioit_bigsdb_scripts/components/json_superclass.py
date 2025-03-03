from typing import Any, Dict

from bioit_mongodb_scripts.model.json_model import JsonReportDict
from .psql import TblAlleleDesignations, TblSequences, TblLoci, TblSchemeMembers, TblClientDbaseLoci


class JsonSuperClass:
    """
    Class containing definitions to insert json typing and gene detection results
    """

    def __init__(self, isolatename: str, species: str,
                 json_report_dict: JsonReportDict, config_data: Dict[str, Any]) -> None:
        """
        :param isolatename: name of the isolate
        :param species: commonly used bioit species name: either genus or specific like stec
        :param json_report_dict: results of sample
        :param config_data: the bigsdb config data
        :return: None
        """
        self._isolatename = isolatename
        self._species = species
        self._json_report_dict = json_report_dict
        self._bigsdb_config_data = config_data

    def _insert_ad_if_needed(self, locus: str, allele_id: str) -> None:
        """
        Inserts given allele designations for given loci if they have not been inserted yet (especially useful for gene detection where multiple hits for the same locus can be found)
        :param locus: locus name
        :param allele_id: allele id (often integers but can be string, but string in sql so treated as such)
        :return: None
        """
        with TblAlleleDesignations(self._species) as isolates_ad_psql_tbl:
            designationpresent = isolates_ad_psql_tbl.count_designations((locus, self._isolatename, allele_id))
            if designationpresent[0][0] == 0:
                isolates_ad_psql_tbl.insert_designation_by_isolatename((locus, self._isolatename, allele_id))

    def _insert_dummy_sequence_if_needed(self, locus: str, allele_id: str) -> None:
        """
        Allele designations for non existing sequences are allowed BUT when clicking on them, a not found error will be received.
        In order to circumvent this, dummy alleles (multitudes of TAG) are inserted; this way users can still see which other samples have this allele designation
        Mostly used in gene detection schemes and other custom non-typing schemes.
        :param locus: locus name
        :param allele_id: allele id (often integers but can be string, but string in sql so treated as such)
        :return:
        """
        with TblSequences(self._species) as seqdef_sequences_psql_tbl:
            present = seqdef_sequences_psql_tbl.count_sequence_allele((locus, allele_id))
            if present[0][0] == 0:
                highest_dummy_sequence = seqdef_sequences_psql_tbl.select_sequence_from_locus((locus,))
                dummysequence: str = 'dummy_1' if len(highest_dummy_sequence) == 0 else '_'.join(['dummy', str(int(highest_dummy_sequence[0][0].split('_')[1]) + 1)])
                seqdef_sequences_psql_tbl.insert_sequence((locus, allele_id, dummysequence))

    def insert_locus_if_needed(self, locus: str, scheme: str) -> None:
        """
        Inserts a given locus and assigns it to a given scheme, if not yet existing
        :param locus: locus name
        :param scheme: scheme name in bigsdb
        :return: None
        """
        with TblLoci(self._species, 'isolates') as isolates_loci_psql_tbl, \
                TblLoci(self._species, 'seqdef') as seqdef_loci_psql_tbl, \
                TblSchemeMembers(self._species, 'isolates') as isolates_schememembers_psql_tbl, \
                TblSchemeMembers(self._species, 'seqdef') as seqdef_schememembers_psql_tbl, \
                TblClientDbaseLoci(self._species) as seqdef_clientdbaseloci_psql_tbl:
            present = seqdef_loci_psql_tbl.count_locus((locus,))
            if present[0][0] == 0:
                # insert into seqdef
                seqdef_loci_psql_tbl.insert_locus_seqdef((locus,))
                seqdef_schememembers_psql_tbl.insert_scheme_member((scheme, locus))
                seqdef_clientdbaseloci_psql_tbl.insert_locus((locus,))
                # insert into isolates
                dbaseurl = ''.join(['/cgi-bin/bigsdb/bigsdb.pl?db=', f'bigsdb_{self._species}_seqdef',
                                    '&page=alleleInfo&locus=', f"{locus}", '&allele_id=[?]'])
                isolates_loci_psql_tbl.insert_locus_isolates((locus, f'bigsdb_{self._species}_seqdef', locus, dbaseurl))
                isolates_schememembers_psql_tbl.insert_scheme_member((scheme, locus))

    def _assign_schememember_if_needed(self, locus: str, scheme: str) -> None:
        """
        Assign given locus to given scheme if not yet in there. Necessary in case loci belong to multiple schemes (although often in that case theyll have a different name).
        :param locus: locus name
        :param scheme: scheme name in bigsdb
        :return: None
        """
        with TblSchemeMembers(self._species, 'isolates') as isolates_schememembers_psql_tbl, \
                TblSchemeMembers(self._species, 'seqdef') as seqdef_schememembers_psql_tbl:
            present = seqdef_schememembers_psql_tbl.count_scheme_member(
                (scheme, locus))
            if present[0][0] == 0:
                # add into seqdef scheme members
                seqdef_schememembers_psql_tbl.insert_scheme_member(
                    (scheme, locus))
                isolates_schememembers_psql_tbl.insert_scheme_member(
                    (scheme, locus))
