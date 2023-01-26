from typing import Final


class PsqlQueries():
    """
    QUERIES
    naming convention (made up by MK):
    DB (seq or iso or uni (universal))
    _ SEL INS UPD or DEL
    what .. (any number of whats separated by _, not applicable for ins and del)
    _TB WHERE  (from which table, or in which table)
    _VAR WHAT (Where which parameters, any nr of which separated by _, indicator for how many arguments to pass to query)
    .
    Group queries by database, then by crud, then by table, then alphabetically
    """
    # TB allele designations
    ISO_UPD_ALLELE_TB_AD_VAR_LOCI_ALLELE: Final[str] = """
        UPDATE allele_designations SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""

    # TB client database loci
    SEQ_INS__TB_CLDBLOCI_VAR_LOCUS: Final[str] = """
        INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) 
        VALUES(1, %s, 1, (SELECT CURRENT_DATE));"""

    # TB isolates
    ISO_DEL__TB_ISO_VAR_ISO_ISO: Final[str] = """
        DELETE FROM isolates WHERE isolate=%s AND id=(SELECT MAX(id) FROM isolates WHERE isolate=%s);"""
    ISO_INS__TB_ISO_VAR_ISO_ISO_ISO_DATE: Final[str] = """
        INSERT INTO isolates(id, isolate, sender, curator, date_entered, datestamp, uploader, latest_analyis_date) 
        VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM isolates) IS NULL THEN 1 
        ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), %s, 1, 1, 
        (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), 
        (SELECT uploader FROM isolates WHERE isolate=%s AND id=(SELECT MAX(id) FROM isolates WHERE isolate=%s)), %s);"""
    ISO_SEL_COUNT_TB_ISO_VAR_ISO: Final[str] = """SELECT COUNT(*) FROM isolates WHERE isolate=%s;"""
    ISO_UPD_NEWV_TB_ISO_VAR_ISO: Final[str] = """
        UPDATE isolates SET new_version=NULL WHERE id=(SELECT MIN(id) FROM isolates WHERE id in (SELECT id FROM isolates WHERE isolate=%s ORDER BY id DESC LIMIT 2));"""
    ISO_UPD_NEWV_TB_ISO_VAR_ISO_ISO_ISO: Final[str] = """
        UPDATE isolates SET new_version=(SELECT MAX(id) FROM isolates WHERE isolate=%s) 
        WHERE isolate=%s AND new_version IS NULL AND id!=(SELECT MAX(id) 
        FROM isolates WHERE isolate=%s);"""

    # TB loci
    ISO_INS__TB_LOCI_VAR_LOCUS_DBNAME_DBID_URL: Final[str] = """
        INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, 
        url, isolate_display, main_display, query_field, analysis, submission_template, 
        curator, date_entered, datestamp) 
        VALUES(%s, 'DNA', 'text', 't', 't', %s, %s, 
        %s, 'allele_only', 'f', 't', 't', 'f', 
        1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
    SEQ_INS__TB_LOCI_VAR_LOCUS: Final[str] = """
        INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) 
        VALUES(%s, 'DNA', 'text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
    UNI_SEL_COUNT_TB_LOCI_VAR_LOCUS: Final[str] = """SELECT COUNT(*) FROM loci WHERE id=%s;"""

    # TB profiles
    SEQ_DEL__TB_PROF_VAR_SCHEME_PROFID: Final[str] = """
        DELETE FROM profiles WHERE scheme_id=(SELECT id FROM schemes WHERE name=%s)
        AND profile_id=%s;"""
    SEQ_INS__TB_PROF_VAR_SCHEME_PROFID: Final[str] = """
        INSERT INTO profiles(scheme_id, 
        profile_id, sender, curator, 
        date_entered, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), 
        %s, 1, 1, 
        (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
    SEQ_SEL_PROFID_TB_PROF_VAR_SCHEME: Final[str] = """
        SELECT profile_id FROM profiles WHERE 
        scheme_id=(SELECT id FROM schemes WHERE name=%s);"""

    # TB profile fields
    SEQ_INS__TB_PROFFIELDS_VAR_SCHEME_SCHFIELD_PROFID_VALUE: Final[str] = """
        INSERT INTO profile_fields(scheme_id, 
        scheme_field, profile_id, value, curator, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), 
        %s, %s, %s, 1, (SELECT CURRENT_DATE));"""

    # TB profile memebers
    SEQ_INS__TB_PROFMEM_VAR_SCHEME_SCHFIELD_PROFID_VALUE: Final[str] = """
        INSERT INTO profile_members(scheme_id, 
        locus, profile_id, allele_id, curator, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), 
        %s, %s, %s, 1, (SELECT CURRENT_DATE));"""

    # TB scheme members
    UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
        INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
    UNI_SEL_COUNT_TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
        SELECT COUNT(*) FROM scheme_members WHERE scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""

    # TB sequences
    SEQ_INS__TB_SEQ_VAR_LOCUS_ALL_SEQ: Final[str] = """
        INSERT INTO sequences(locus, allele_id, sequence, status,sender,curator, date_entered, datestamp) \
        VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
    SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS: Final[str] = """SELECT allele_id FROM sequences WHERE locus=%s;"""
    SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS_SEQ: Final[str] = """
        SELECT allele_id FROM sequences WHERE locus=%s AND sequence=%s;"""
    SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS: Final[str] = """
        SELECT COUNT(*) FROM sequences WHERE 
        locus=%s AND sequence='null allele';"""
    SEQ_UPD_ALLELE_TB_SEQ_VAR_LOCUS_ALLELE: Final[str] = """
        UPDATE sequences SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""