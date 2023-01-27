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
    # TBL allele designations
    ISO_DEL__TB_AD_VAR_LOCUS: Final[str] = """DELETE FROM allele_designations WHERE locus LIKE %s;"""
    ISO_INS__TB_AD_VAR_LOCUS_ISO_ALLELE: Final[str] = """
        INSERT INTO allele_designations(locus, isolate_id, 
        allele_id, status, method, sender, 
        curator, date_entered, datestamp) 
        VALUES(%s, %s, 
        %s, 'confirmed', 'automatic', 1, 
        1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
    ISO_SEL_COUNT_TB_AD_VAR_LOCUS_ISO_ALLELE: Final[str] = """
        SELECT COUNT(*) FROM allele_designations WHERE 
        locus=%s AND isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s) AND allele_id=%s;"""
    ISO_UPD_ALLELE_TB_AD_VAR_LOCUS_ALLELE: Final[str] = """
        UPDATE allele_designations SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""

    # TBL client database loci
    SEQ_INS__TB_CLDBLOCI_VAR_LOCUS: Final[str] = """
        INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) 
        VALUES(1, %s, 1, (SELECT CURRENT_DATE));"""

    # TBL extended attribute values bool
    ISO_INS__TB_EAVB_VAR_ISO_FIELD_VAL: Final[str] = """
        INSERT INTO eav_boolean(isolate_id, field, value) 
        VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""

    # TBL extended attribute values text
    ISO_DEL__TB_EAVT_VAR_ID_FIELD: Final[str] = """DELETE FROM eav_text WHERE isolate_id=%s AND field=%s;"""
    ISO_INS__TB_EAVT_VAR_ID_FIELD_VAL: Final[str] = """INSERT INTO eav_text(isolate_id, field, value) VALUES(%s, %s, %s);"""
    ISO_INS__TB_EAVT_VAR_ISO_FIELD_VAL: Final[str] = """
        INSERT INTO eav_text(isolate_id, field, value) 
        VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""

    # TBL extended attribute values text hidden
    ISO_SEL_ID_VAL_ISO_TB_EAVTH_VAR_FIELD: Final[str] = """
        SELECT eav_text_hidden.isolate_id, eav_text_hidden.value, isolates.isolate FROM eav_text_hidden 
        LEFT JOIN isolates ON isolates.id = eav_text_hidden.isolate_id WHERE eav_text_hidden.field = %s;"""
    ISO_INS__TB_EAVTH_VAR_ISO_FIELD_VAL: Final[str] = """
            INSERT INTO eav_text_hidden(isolate_id, field, value) 
            VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s), %s, %s);"""

    # TBL history
    ISO_INS__TB_HIST_VAR_ID_MESS: Final[str] = """
        INSERT INTO history(isolate_id, timestamp, action, curator) 
        VALUES(%s, (SELECT NOW()::TIMESTAMP), %s, 1);"""
    ISO_INS__TB_HIST_VAR_ISO_MESS: Final[str] = """
        INSERT INTO history(isolate_id, timestamp, action, curator) 
        VALUES((SELECT MAX(id) FROM isolates WHERE isolate=%s),(SELECT NOW()::TIMESTAMP), %s, 1);"""

    # TBL isolates
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

    # TBL loci
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

    # TBL locus descriptions
    SEQ_DEL__TB_LOCDES_VAR_LOCUS: Final[str] = """DELETE FROM locus_descriptions WHERE locus LIKE %s;"""

    SEQ_INS__TB_LOCDES_VAR_LOCUS_PROD_DES: Final[str] = """
        INSERT INTO locus_descriptions(locus, product, description, datestamp, curator) 
        VALUES(%s, %s, %s ,(SELECT CURRENT_DATE), 1);"""

    # TBL profiles
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

    # TBL profile fields
    SEQ_INS__TB_PROFFIELDS_VAR_SCHEME_SCHFIELD_PROFID_VALUE: Final[str] = """
        INSERT INTO profile_fields(scheme_id, 
        scheme_field, profile_id, value, curator, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), 
        %s, %s, %s, 1, (SELECT CURRENT_DATE));"""

    # TBL profile members
    SEQ_INS__TB_PROFMEM_VAR_SCHEME_SCHFIELD_PROFID_VALUE: Final[str] = """
        INSERT INTO profile_members(scheme_id, 
        locus, profile_id, allele_id, curator, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), 
        %s, %s, %s, 1, (SELECT CURRENT_DATE));"""

    # TBL scheme members
    UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
        INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
    UNI_SEL_COUNT_TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
        SELECT COUNT(*) FROM scheme_members WHERE scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""

    # TBL sequences
    SEQ_INS__TB_SEQ_VAR_LOCUS_ALLELE_SEQ: Final[str] = """
        INSERT INTO sequences(locus, allele_id, sequence, status, sender,curator, date_entered, datestamp) \
        VALUES(%s, %s, %s, 'unchecked', 1, 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
    SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS: Final[str] = """SELECT allele_id FROM sequences WHERE locus=%s;"""
    SEQ_SEL_SEQUENCE_TB_SEQ_VAR_LOCUS: Final[str] = """SELECT sequence FROM sequences WHERE locus=%s ORDER BY CHAR_LENGTH(sequence) DESC, sequence DESC LIMIT 1;"""
    SEQ_SEL_ALLELE_TB_SEQ_VAR_LOCUS_SEQ: Final[str] = """
        SELECT allele_id FROM sequences WHERE locus=%s AND sequence=%s;"""
    SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS: Final[str] = """
        SELECT COUNT(*) FROM sequences WHERE 
        locus=%s AND sequence='null allele';"""
    SEQ_SEL_COUNT_TB_SEQ_VAR_LOCUS_ALLELE: Final[str] = """
        SELECT COUNT(*) FROM sequences WHERE 
        locus=%s AND allele_id=%s;"""
    SEQ_UPD_ALLELE_TB_SEQ_VAR_LOCUS_ALLELE: Final[str] = """
        UPDATE sequences SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""

    # TBL sequence bin
    SEQ_SEL_COUNT_TB_SEQBIN_VAR_ISO: Final[str] = """
        SELECT COUNT(*) FROM sequence_bin WHERE isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s);"""
    SEQ_INS__TB_SEQBIN_VAR_ISO_SEQ_NAME: Final[str] = """
        INSERT INTO sequence_bin(id, 
        isolate_id, 
        remote_contig, sequence, original_designation, sender, 
        curator, date_entered, datestamp) 
        VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM sequence_bin) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM sequence_bin)+1) END), 
        (SELECT MAX(id) FROM isolates WHERE isolate=%s), 
        'f', %s, %s, 1, 
        1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE))"""

    # TBL submissions
    ISO_SEL_ID_VALUE_OUTCOME_EMAIL_TYPE_TB_SUB_VAR_: Final[str] = """
        SELECT submissions.id, isolate_submission_isolates.value, submissions.outcome, users.email, submissions.validation_type 
        FROM submissions 
        LEFT JOIN users ON users.id = submissions.curator 
        LEFT JOIN isolate_submission_isolates ON isolate_submission_isolates.submission_id = submissions.id 
        WHERE submissions.status='closed' and isolate_submission_isolates.field='isolate_id';"""

    ISO_UPD_STATUS_TB_SUB_VAR_ID: Final[str] = """
        UPDATE submissions SET status='validation_sent_to_bioit_platform' WHERE id=%s;"""