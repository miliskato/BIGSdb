from typing import Final


class PsqlQueries:
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
    # General table existence check
    SEL_TABLE_EXISTS: Final[str] = """SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s);"""

    # TBL alert details field order
    ISO_INS__TB_ALDEFO_VAR_FIELD_INDEX: Final[str] = """
        INSERT INTO alert_details_field_order(alert_id, field, index) 
        VALUES((SELECT MAX(id::int) FROM alerts), %s, %s);"""

    # TBL alert details
    ISO_INS__TB_ALDE_VAR_FIELD_VALUE: Final[str] = """
        INSERT INTO alert_details (alert_id, index, field, value) 
        VALUES((SELECT MAX(id::int) FROM alerts), 1, %s, %s);"""
    ISO_SEL_ALID_TYPE_TB_ALDE_VAR_ISOLATE_METH: Final[str] = """
        SELECT alert_id, type FROM alert_details LEFT JOIN alerts ON 
        alerts.id = alert_details.alert_id WHERE field = 'isolate_id' AND value = 
        (SELECT CAST(id AS TEXT) FROM isolates WHERE isolate=%s) and method = %s;"""
    ISO_UPD_VAL_TB_ALDE_VAR_ALID_FIELD: Final[str] = """
        UPDATE alert_details SET value = %s WHERE alert_id = %s AND field = %s;"""

    # TBL alerts
    ISO_INS__TB_AL_VAR_TYPE_METH: Final[str] = """
        INSERT INTO alerts(id, 
        type, method, submitter, date_submitted, 
        datestamp, status, email) 
        VALUES ((SELECT CASE WHEN (SELECT MAX(id::int) FROM alerts) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id::int) FROM alerts)+1) END), 
        %s, %s, 1, (SELECT CURRENT_DATE), 
        (SELECT CURRENT_DATE), 'pending', true);"""
    ISO_UPD_TYPE_STATUS_TB_ALDE_VAR_ALID: Final[str] = """
        UPDATE alerts SET type = 'alert' AND status = 'pending' WHERE alert_id = %s;"""

    # TBL allele designations
    ISO_DEL__TB_AD_VAR_LOCUS: Final[str] = """DELETE FROM allele_designations WHERE locus LIKE %s;"""
    ISO_DEL__TB_AD_VAR_ISO: Final[str] = """DELETE FROM allele_designations WHERE isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_INS__TB_AD_VAR_LOCUS_ID_ALLELE: Final[str] = """
        INSERT INTO allele_designations(locus, isolate_id, 
        allele_id, status, method, sender, 
        curator, date_entered, datestamp) 
        VALUES(%s, %s, 
        %s, 'confirmed', 'automatic', 1, 
        1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
    ISO_INS__TB_AD_VAR_LOCUS_ISO_ALLELE: Final[str] = """
        INSERT INTO allele_designations(locus, isolate_id, 
        allele_id, status, method, sender, 
        curator, date_entered, datestamp) 
        VALUES(%s, (SELECT id FROM isolates WHERE isolate=%s), 
        %s, 'confirmed', 'automatic', 1, 
        1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
    ISO_SEL_COUNT_TB_AD_VAR_LOCUS_ISO_ALLELE: Final[str] = """
        SELECT COUNT(*) FROM allele_designations WHERE 
        locus=%s AND isolate_id=(SELECT id FROM isolates WHERE isolate=%s) AND allele_id=%s;"""
    ISO_UPD_ALLELE_TB_AD_VAR_LOCUS_ALLELE: Final[str] = """
        UPDATE allele_designations SET allele_id = %s WHERE locus=%s AND allele_id=%s;"""

    # TBL classification groups
    SEQ_DEL__TB_CLGR_VAR_CGSCHID: Final[str] = """DELETE FROM classification_groups WHERE cg_scheme_id=%s;"""
    SEQ_INS__TB_CLGR_VAR_CGSCHID_GRID: Final[str] = """
        INSERT INTO classification_groups(cg_scheme_id, group_id, active, curator, datestamp) 
        VALUES(%s, %s, true, 1, (SELECT CURRENT_DATE));"""
    SEQ_SEL_COUNT_TB_CLGR_VAR_CGSCHID_GRID: Final[str] = """
        SELECT COUNT(*) FROM classification_groups WHERE cg_scheme_id=%s AND group_id=%s;"""
    SEQ_UPD_ACTIVE_TB_CLGR_VAR_CGSCHID_GRID: Final[str] = """
        UPDATE classification_groups SET active = false WHERE cg_scheme_id=%s AND group_id=%s;"""

    # TBL classification group profiles
    SEQ_INS__TB_CLGRPR_VAR_CGSCHID_GRID_PRID_SCHEME: Final[str] = """
        INSERT INTO classification_group_profiles(cg_scheme_id, group_id, profile_id, 
        scheme_id, curator, datestamp) 
        VALUES(%s, %s, %s, 
        (SELECT id FROM schemes WHERE name = %s), 1, (SELECT CURRENT_DATE));"""
    SEQ_SEL_GRID_TB_CLGRPR_VAR_CGSCHID_PRID: Final[str] = """
        SELECT group_id FROM classification_group_profiles WHERE cg_scheme_id=%s AND profile_id=%s;"""
    SEQ_UPD_GRID_TB_CLGRPR_VAR_CGSCHID_PRID: Final[str] = """
        UPDATE classification_group_profiles SET group_id = %s 
        WHERE cg_scheme_id=%s AND profile_id='%s';"""

    # TBL classification group profile history
    SEQ_INS__TB_CLGRPRHIST_VAR_SCHEME_PRID_CGSCHID_PREVGR: Final[str] = """
        INSERT INTO classification_group_profile_history(timestamp, scheme_id, 
        profile_id, cg_scheme_id, previous_group) 
        VALUES((SELECT CURRENT_TIMESTAMP), (SELECT id FROM schemes WHERE name = %s),
        %s, %s, %s);"""

    # TBL classification schemes
    SEQ_SEL_CGSCHID_TB_CLSCH_VAR_INCTHR: Final[str] = """
        SELECT id FROM classification_schemes WHERE inclusion_threshold=%s;"""
    SEQ_SEL_CGSCHID_INCTHR_TB_CLSCH_VAR_: Final[str] = """
        SELECT id, inclusion_threshold from classification_schemes;"""
    SEQ_INS__TB_CLSCH_VAR_CGSCHID_SCHEME_NAME_DESC_INCTHR_CGSCHID: Final[str] = """
        INSERT INTO classification_schemes(id, scheme_id, name, description, inclusion_threshold, 
        use_relative_threshold, display_order, status, curator, datestamp) 
        VALUES(%s, (SELECT id FROM schemes WHERE name=%s), %s, %s, %s, 
        false, %s, 'experimental', 1, (SELECT CURRENT_DATE));"""
    ISO_INS__TB_CLSCH_VAR_CGSCHID_SCHEME_NAME_DESC_INCTHR_CGSCHID_CGSCHID: Final[str] = """
        INSERT INTO classification_schemes(id, scheme_id, name, description, inclusion_threshold, 
        use_relative_threshold, seqdef_cscheme_id, display_order, status, curator, datestamp) 
        VALUES(%s, (SELECT id FROM schemes WHERE name=%s), %s, %s, %s, 
        false, %s, %s, 'experimental', 1, (SELECT CURRENT_DATE));"""

    # TBL client database loci
    SEQ_INS__TB_CLDBLOCI_VAR_LOCUS: Final[str] = """
        INSERT INTO client_dbase_loci(client_dbase_id, locus, curator, datestamp) 
        VALUES(1, %s, 1, (SELECT CURRENT_DATE));"""

    # TBL extended attribute values fields
    ISO_INS__TB_EAVF_VAR_FIELD: Final[str] = """
        INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) 
        VALUES(%s, 'boolean', 'NCBI 16S', '', 't', 't', (SELECT CURRENT_DATE), 1);"""
    ISO_INS__TB_EAVF_VAR_FIELD_CAT: Final[str] = """
        INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) 
        VALUES(%s, 'text', %s, 't', 't', 't', (SELECT CURRENT_DATE), 1);"""
    ISO_SEL_COUNT_TB_EAVF_VAR_FIELD: Final[str] = """
        SELECT COUNT(*) FROM eav_fields WHERE category='NCBI 16S' AND field=%s;"""
    ISO_SEL_FIELD_TB_EAVF_VAR_: Final[str] = """SELECT field FROM eav_fields WHERE category='AMR detection';"""
    ISO_SEL_FIELD_TB_EAVF_VAR_CAT: Final[str] = """SELECT field FROM eav_fields WHERE category=%s;"""
    ISO_SEL_FIELD_TB_EAVF_VAR_FIELD: Final[str] = """SELECT field FROM eav_fields WHERE field LIKE %s;"""
    ISO_SEL_COUNT_TB_EAVF_VAR_FIELD_CAT: Final[str] = """SELECT count(*) FROM eav_fields WHERE field=%s AND category=%s ;"""

    # TBL extended attribute values bool
    ISO_DEL__TB_EAVB_VAR_ISO: Final[str] = """
        DELETE FROM eav_boolean where isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_INS__TB_EAVB_VAR_ISO_FIELD_VAL: Final[str] = """
        INSERT INTO eav_boolean(isolate_id, field, value) 
        VALUES((SELECT id FROM isolates WHERE isolate=%s), %s, %s);"""

    # TBL extended attribute values float
    ISO_DEL__TB_EAVFL_VAR_ISO: Final[str] = """
        DELETE FROM eav_float WHERE isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_INS__TB_EAVFL_VAR_ISO_FIELD_VAL: Final[str] = """
        INSERT INTO eav_float(isolate_id, field, value) 
        VALUES((SELECT id FROM isolates WHERE isolate=%s), %s, %s);"""

    # TBL extended attribute values int
    ISO_DEL__TB_EAVI_VAR_ISO: Final[str] = """
        DELETE FROM eav_int where isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_INS__TB_EAVI_VAR_ISO_FIELD_VAL: Final[str] = """
        INSERT INTO eav_int(isolate_id, field, value) 
        VALUES((SELECT id FROM isolates WHERE isolate=%s), %s, %s);"""
    # TBL extended attribute values text
    ISO_DEL__TB_EAVT_VAR_ISO: Final[str] = """DELETE FROM eav_text WHERE isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_DEL__TB_EAVT_VAR_ID_FIELD: Final[str] = """DELETE FROM eav_text WHERE isolate_id=%s AND field=%s;"""
    ISO_DEL__TB_TPISOSCHFIELD_VAR_SCHID_ISO: Final[str] = """DELETE FROM temp_isolates_scheme_fields_%s WHERE id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_INS__TB_EAVT_VAR_ID_FIELD_VAL: Final[str] = """
        INSERT INTO eav_text(isolate_id, field, value) VALUES(%s, %s, %s);"""
    ISO_INS__TB_EAVT_VAR_ISO_FIELD_VAL: Final[str] = """
        INSERT INTO eav_text(isolate_id, field, value) 
        VALUES((SELECT id FROM isolates WHERE isolate=%s), %s, %s);"""
    ISO_UPD_VAL_TB_EAVT_VAR_ID_FIELD: Final[str] = """
        UPDATE eav_text SET value = %s WHERE isolate_id=%s AND field=%s;"""
    ISO_SEL_COUNT_TB_EAVT_VAR_ID_FIELD: Final[str] = """
        SELECT COUNT(*) FROM eav_text WHERE isolate_id=%s AND field=%s;"""
    ISO_SEL_COUNT_TB_EAVT_VAR_FIELD: Final[str] = """
        SELECT COUNT(*) FROM eav_text WHERE field=%s;"""
    # TBL extended attribute values text hidden
    ISO_INS__TB_EAVTH_VAR_ISO_FIELD_VAL: Final[str] = """
        INSERT INTO eav_text_hidden(isolate_id, field, value) 
        VALUES((SELECT id FROM isolates WHERE isolate=%s), %s, %s);"""
    ISO_DEL__TB_EAVTH_VAR_ISO: Final[str] = """
        DELETE FROM eav_text_hidden WHERE isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_SEL_ID_VAL_ISO_TB_EAVTH_VAR_FIELD: Final[str] = """
        SELECT eav_text_hidden.isolate_id, eav_text_hidden.value, isolates.isolate FROM eav_text_hidden 
        LEFT JOIN isolates ON isolates.id = eav_text_hidden.isolate_id WHERE eav_text_hidden.field = %s;"""
    ISO_SEL_VERSION_TB_EAVTH_VAR_ISO: Final[str] = """
        SELECT value FROM eav_text_hidden WHERE field='mongo_results_version' AND 
        isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""

    # TBL failed_insertions
    ISO_INS__TB_FAILINS_VAR_MSGID_PSEUDOID: Final[str] = """
        INSERT INTO failed_insertions(message_id, pseudo_id, timestamp, comment) VALUES(%s, %s, (SELECT NOW()::TIMESTAMP), 'Insertion started');"""
    ISO_UPD_COM_TB_FAILINS_VAR_MSGID: Final[str] = """
        UPDATE failed_insertions set comment = %s WHERE message_id = %s;"""
    ISO_DEL__TB_FAILINS_VAR_MSGID: Final[str] = """
        DELETE FROM failed_insertions WHERE message_id = %s;"""

    # TBL history
    ISO_INS__TB_HIST_VAR_ID_MESS: Final[str] = """
        INSERT INTO history(isolate_id, timestamp, action, curator) 
        VALUES(%s, (SELECT NOW()::TIMESTAMP), %s, 1);"""
    ISO_INS__TB_HIST_VAR_ISO_MESS: Final[str] = """
        INSERT INTO history(isolate_id, timestamp, action, curator) 
        VALUES((SELECT id FROM isolates WHERE isolate=%s),(SELECT NOW()::TIMESTAMP), %s, 1);"""

    # TBL isolates
    ISO_DEL__TB_ISO_VAR_ISO_ISO: Final[str] = """
        DELETE FROM isolates WHERE isolate=%s;"""
    ISO_UPD__TB_ISO_VAR_ISO_ISO_ISO_DATE: Final[str] = """
        UPDATE isolates SET (date_entered, datestamp, latest_analysis_date) = 
        ((SELECT CURRENT_DATE),(SELECT CURRENT_DATE), %s) WHERE isolate=%s;"""
    ISO_INS__TB_ISO_VAR_ISO_UPL_DATE_ISODATE: Final[str] = """
        INSERT INTO isolates(id, 
        isolate, sender, curator, date_entered, datestamp, uploader, latest_analysis_date, isolation_date)
        VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM isolates) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM isolates)+1) END), 
        %s, 1, 1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE), %s, %s, %s);"""
    ISO_SEL_COUNT_TB_ISO_VAR_ISO: Final[str] = """SELECT COUNT(*) FROM isolates WHERE isolate=%s;"""
    ISO_SEL_ANADATE_TB_ISO_VAR_ISO: Final[str] = """
        SELECT latest_analysis_date FROM isolates WHERE id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_SEL_ID_ISO_DATE_CGST_TB_ISO_VAR_SCHID_SCHID_SCHID_CGSTS_DATE1_DATE2: Final[str] = """
        SELECT isolates.id, isolates.isolate, isolates.isolation_date, cgst FROM isolates LEFT JOIN 
        temp_isolates_scheme_fields_%s ON isolates.id = temp_isolates_scheme_fields_%s.id 
        WHERE temp_isolates_scheme_fields_%s.cgst IN %s AND isolates.isolation_date>%s AND isolates.isolation_date<=%s;"""
    ISO_SEL_ID_ISO_DATE_CGST_TB_ISO_VAR_SCHID_SCHID_SCHID_CGSTS: Final[str] = """
        SELECT isolates.id, isolates.isolate, isolates.isolation_date, cgst FROM isolates LEFT JOIN 
        temp_isolates_scheme_fields_%s ON isolates.id = temp_isolates_scheme_fields_%s.id 
        WHERE temp_isolates_scheme_fields_%s.cgst IN %s;"""
    ISO_SEL_ID_ISO_DATE_CGST_CLGR_TB_ISO_VAR_CSCHID_SCHID_SCHID_CSCHID_CSCHID_CSCHID_CSCHID_CGST_DATE1_DATE2: Final[str] = """
        SELECT isolates.id, isolates.isolate, isolates.isolation_date, cgst, temp_cscheme_%s.group_id FROM isolates LEFT JOIN 
        temp_isolates_scheme_fields_%s ON isolates.id = temp_isolates_scheme_fields_%s.id 
        LEFT JOIN temp_cscheme_%s on cgst = temp_cscheme_%s.profile_id
        WHERE temp_cscheme_%s.group_id = (SELECT group_id FROM temp_cscheme_%s WHERE profile_id = %s)
        AND isolates.isolation_date>%s AND isolates.isolation_date<=%s;"""
    ISO_SEL_ID_ISO_DATE_CGST_CLGR_TB_ISO_VAR_CSCHID_SCHID_SCHID_CSCHID_CSCHID_CSCHID_CSCHID_CGST: Final[str] = """
        SELECT isolates.id, isolates.isolate, isolates.isolation_date, cgst, temp_cscheme_%s.group_id FROM isolates LEFT JOIN 
        temp_isolates_scheme_fields_%s ON isolates.id = temp_isolates_scheme_fields_%s.id 
        LEFT JOIN temp_cscheme_%s on cgst = temp_cscheme_%s.profile_id
        WHERE temp_cscheme_%s.group_id = (SELECT group_id FROM temp_cscheme_%s WHERE profile_id = %s);"""
    ISO_SEL_CGST_TB_ISO_VAR_SCHID_ISO: Final[str] = """
        SELECT cgst FROM isolates LEFT JOIN 
        temp_isolates_scheme_fields_%s USING (id)
        WHERE isolates.isolate = %s;"""
    ISO_SEL_ISO_DATE_TB_ISO_VAR_ISOS: Final[str] = """
        SELECT isolate, isolation_date FROM isolates WHERE
        isolate IN %s AND isolation_date IS NOT NULL;"""
    ISO_SEL_ID_TB_ISO_VAR_ISO: Final[str] = """SELECT id FROM isolates WHERE isolate=%s;"""
    ISO_SEL_VALDATES_TB_ISO_VAR_ISO: Final[str] = """
        SELECT validation_date FROM isolates WHERE isolate=%s ORDER BY id DESC LIMIT 2;"""
    ISO_UPD_NEWV_TB_ISO_VAR_ISO: Final[str] = """
        UPDATE isolates SET new_version=NULL WHERE 
        id=(SELECT MIN(id) FROM isolates WHERE id IN (SELECT id FROM isolates WHERE isolate=%s ORDER BY id DESC LIMIT 2));"""
    ISO_UPD_VALTYPE_VALCUR_VALDATE_TB_ISO_VAR_ID: Final[str] = """
        UPDATE isolates SET 
        validation_type = %s, 
        validation_curator = %s, 
        validation_date = %s
        WHERE id=%s;"""
    ISO_SEL_ISOLATE_ID: Final[str] = """
        SELECT isolate FROM isolates;"""

    # TBL isolate submission field order
    ISO_INS__TB_ISOSUBFO_VAR_FIELD_INDEX: Final[str] = """
        INSERT INTO isolate_submission_field_order(submission_id, field, index) 
        VALUES((SELECT MAX(id::int) FROM submissions WHERE id ~ '^[0-9]+$'), %s, %s);"""

    # TBL isolate submission isolates
    ISO_INS__TB_ISOSUBISO_VAR_FIELD_VALUE: Final[str] = """
        INSERT INTO isolate_submission_isolates (submission_id, index, field, value) 
        VALUES((SELECT MAX(id::int) FROM submissions WHERE id ~ '^[0-9]+$'), 1, %s, %s);"""
    ISO_SEL_ALL_TB_ISOSUBISO_VAR_SUBID: Final[str] = """
        SELECT * FROM isolate_submission_isolates WHERE submission_id=%s;"""

    # TBL jobs
    JOB_SEL_PID_STARTED_JOBS_TB_JOBS: Final[str] = """
        SELECT pid, module, stage FROM jobs WHERE status = 'started' ;"""
    JOBS_SET_FAILED_STATUS: Final[str] = """
        UPDATE jobs SET status = 'failed' WHERE pid = %s;"""
    # TBL loci
    ISO_INS__TB_LOCI_VAR_LOCUS_DBNAME_DBID_URL: Final[str] = """
        INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, dbase_name, dbase_id, 
        url, isolate_display, main_display, query_field, analysis, submission_template, 
        curator, date_entered, datestamp) 
        VALUES(%s, 'DNA', 'text', 't', 't', %s, %s, 
        %s, 'allele_only', 'f', 't', 't', 'f', 
        1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
    SEQ_SEL__TB_SCHEME_MBR_VAR_SCHEME_ID: Final[str] = """
        SELECT locus FROM scheme_members WHERE scheme_id=(SELECT id FROM schemes WHERE name = %s);"""
    SEQ_INS__TB_LOCI_VAR_LOCUS: Final[str] = """
        INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, curator, date_entered, datestamp) 
        VALUES(%s, 'DNA', 'text', 't', 't', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));"""
    UNI_SEL_COUNT_TB_LOCI_VAR_LOCUS: Final[str] = """SELECT COUNT(*) FROM loci WHERE id=%s;"""

    # TBL locus descriptions
    SEQ_DEL__TB_LOCDES_VAR_LOCUS: Final[str] = """DELETE FROM locus_descriptions WHERE locus LIKE %s;"""

    SEQ_INS__TB_LOCDES_VAR_LOCUS_PROD_DES: Final[str] = """
        INSERT INTO locus_descriptions(locus, product, description, datestamp, curator) 
        VALUES(%s, %s, %s ,(SELECT CURRENT_DATE), 1);"""

    # TBL mapping table
    ISO_INS__TB_MT_VAR_ISO_PSEUDOID: Final[str] = """
        INSERT INTO mapping_table (isolate_id, isolate, pseudo_id) VALUES((SELECT id FROM isolates WHERE isolate = %s),%s, %s);"""
    ISO_SEL_ID_TB_MT_VAR_PSEUDOID: Final[str] = """
        SELECT isolate_id FROM mapping_table WHERE pseudo_id=%s;"""
    ISO_SEL_PSEUDOID_TB_MT_VAR_ISO: Final[str] = """
        SELECT pseudo_id FROM mapping_table WHERE isolate=%s;"""

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

    # TBL rejected isolates
    ISO_INS__TB_REJISO_VAR_ISO_DATE_REJREAS_TYPE_REPORT: Final[str] = """
        INSERT INTO rejected_isolates(id, isolate, insertion_date, rejection_reasons, insertion_type, report_link, status) \
        VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM rejected_isolates) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM rejected_isolates)+1) END), \
        %s, %s, %s, %s, %s, 'pending');"""
    ISO_DEL__TB_REJISO_VAR_ISO: Final[str] = """
        DELETE FROM rejected_isolates WHERE isolate=%s;"""
    ISO_SEL_EXISTS_TB_REJISO_VAR_ISO: Final[str] = """
        SELECT EXISTS(SELECT 1 FROM rejected_isolates WHERE isolate=%s);"""
    ISO_SEL_MAX_REJISO: Final[str] = """
        SELECT MAX(id) FROM rejected_isolates"""

    # TBL schemes
    UNI_SEL_ID_TB_SCHEME_VAR_: Final[str] = """
        SELECT id FROM schemes WHERE name = 'cgMLST';"""
    UNI_SEL_ID_TB_SCHEME_VAR_NAME: Final[str] = """
        SELECT id FROM schemes WHERE name = %s;"""

    # TBL scheme members
    UNI_SEL_EXISTS_TB_SCHMEM_VAR_SCHID: Final[str] = """
         SELECT EXISTS (SELECT * FROM scheme_members WHERE scheme_id=%s);"""
    UNI_INS__TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
        INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) 
        VALUES((SELECT id FROM schemes WHERE name=%s), %s, 1, (SELECT CURRENT_DATE));"""
    UNI_SEL_COUNT_TB_SCHMEM_VAR_SCHEME_LOCUS: Final[str] = """
        SELECT COUNT(*) FROM scheme_members WHERE scheme_id=(SELECT id FROM schemes WHERE name=%s) AND locus=%s;"""
    UNI_SEL_LOCUS_TB_SCHMEM_VAR_: Final[str] = """
        SELECT locus FROM scheme_members WHERE scheme_id = (SELECT id FROM schemes WHERE name = 'AMR_detection_WHO');"""

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
    ISO_INS__TB_SEQBIN_VAR_ISO_SEQ_NAME: Final[str] = """
        INSERT INTO sequence_bin(id, 
        isolate_id, 
        remote_contig, sequence, original_designation, sender, 
        curator, date_entered, datestamp) 
        VALUES((SELECT CASE WHEN (SELECT MAX(id) FROM sequence_bin) IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id) FROM sequence_bin)+1) END), 
        (SELECT id FROM isolates WHERE isolate=%s), 
        'f', %s, %s, 1, 
        1, (SELECT CURRENT_DATE),(SELECT CURRENT_DATE));"""
    ISO_DEL__TB_SEQBIN_VAR_ISO: Final[str] = """
        DELETE FROM sequence_bin WHERE isolate=%s;"""
    ISO_SEL_COUNT_TB_SEQBIN_VAR_ISO: Final[str] = """
        SELECT COUNT(*) FROM sequence_bin WHERE isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""
    ISO_UPD_REVERSE_TB_SEQBIN_VAR_ISO_ISO: Final[str] = """
        UPDATE sequence_bin SET isolate_id=(SELECT id FROM isolates WHERE isolate=%s);"""

    # TBL seq bin stats
    ISO_UPD_REVERSE_TB_SEQBINSTATS_VAR_ISO_ISO: Final[str] = """
        UPDATE seqbin_stats SET isolate_id=(SELECT MIN(id) FROM isolates WHERE id in (SELECT id FROM isolates WHERE isolate=%s ORDER BY id DESC LIMIT 2)) 
        WHERE isolate_id=(SELECT MAX(id) FROM isolates WHERE isolate=%s);"""

    # TBL submissions
    ISO_SEL_ID_VALUE_OUTCOME_EMAIL_TYPE_TB_SUB_VAR_SUBID: Final[str] = """
        SELECT submissions.id, isolate_submission_isolates.value, submissions.outcome, users.email, submissions.quality, submissions.resequencing
        FROM submissions 
        LEFT JOIN users ON users.id = submissions.curator 
        LEFT JOIN isolate_submission_isolates ON isolate_submission_isolates.submission_id = submissions.id 
        WHERE submissions.status='closed' and isolate_submission_isolates.field='isolate_id' and submissions.id=%s;"""
    ISO_UPD_STATUS_TB_SUB_VAR_ID: Final[str] = """
        UPDATE submissions SET status='validation_sent_to_bioit_platform' WHERE id=%s;"""
    ISO_INS__TB_SUB_VAR_QUAL_RESEQ: Final[str] = """
        INSERT INTO submissions(id, 
        type, submitter, date_submitted, 
        datestamp, status, email, quality, resequencing) 
        VALUES ((SELECT CASE WHEN (SELECT MAX(id::int) FROM submissions WHERE id ~ '^[0-9]+$') IS NULL THEN 1 ELSE (SELECT(SELECT MAX(id::int) FROM submissions WHERE id ~ '^[0-9]+$')+1) END), 
        'isolates', 1, (SELECT CURRENT_DATE), 
        (SELECT CURRENT_DATE), 'pending', true, %s, %s);"""
    ISO_SEL_ID_TB_SUB_VAR_STATUS: Final[str] = """
        SELECT id FROM submissions WHERE outcome = 'good' AND status = 'closed' AND id LIKE 'BIGSdb_%';"""
    ISO_SEL_SUBID_TB_SUB_VAR_: Final[str] = """
        SELECT id FROM submissions WHERE outcome = 'good' AND status = 'closed' AND quality = 'warning' and resequencing = 'no';"""
    ISO_UPD_STATUS_OUTCOME_TB_SUB_VAR_: Final[str] = """
        UPDATE submissions SET (status, outcome) = ('closed', 'good') WHERE ( quality = 'warning' AND resequencing = 'no' AND OUTCOME IS NULL);"""
    ISO_INSERT_GENERIC_LAB_METADATA_TEMPLATE: Final[str] = "UPDATE isolates SET {} WHERE isolate=%s;"

