-- migrate:up
ALTER TABLE isolates
    DROP COLUMN latitude,
    DROP COLUMN longitude,
    ADD COLUMN symptom_asymptomatic text,
    ADD COLUMN symptom_gastroenteritis text,
    ADD COLUMN symptom_sepsis text,
    ADD COLUMN symptom_urinary_tract_infection text,
    ADD COLUMN symptom_unknown text,
    DROP COLUMN clinical_info,
    ADD COLUMN mic_azm_I text,
    ADD COLUMN mic_smx real,
    ADD COLUMN mic_tgc_I text,
    ADD COLUMN mic_tmp_I text,
    ALTER COLUMN mic_azm TYPE real USING mic_azm::real;
/* All the forms of ALTER TABLE that act on a single table, except RENAME, SET SCHEMA, ATTACH PARTITION, and 
   DETACH PARTITION can be combined into a list of multiple alterations to be applied together.  */
ALTER TABLE isolates
    RENAME COLUMN mic_cox_1 TO mic_cox_I;
ALTER TABLE isolates
    RENAME COLUMN mic_chl_1 TO mic_chl_I;
ALTER TABLE isolates
    RENAME COLUMN mic_cip_1 TO mic_cip_I;
ALTER TABLE isolates
    RENAME COLUMN mic_pen_1 TO mic_pen_I;
ALTER TABLE isolates
    RENAME COLUMN mic_rif_1 TO mic_rif_I;
ALTER TABLE isolates
    RENAME COLUMN mic_amo_1 TO mic_amo_I;
ALTER TABLE isolates
    RENAME COLUMN mic_amp_1 TO mic_amp_I;
ALTER TABLE isolates
    RENAME COLUMN mic_caz_1 TO mic_caz_I;
ALTER TABLE isolates
    RENAME COLUMN mic_col_1 TO mic_col_I;
ALTER TABLE isolates
    RENAME COLUMN mic_etp_1 TO mic_etp_I;
ALTER TABLE isolates
    RENAME COLUMN mic_gmn_1 TO mic_gmn_I;
ALTER TABLE isolates
    RENAME COLUMN mic_mem_1 TO mic_mem_I;
ALTER TABLE isolates
    RENAME COLUMN mic_smx_1 TO mic_smx_I;
ALTER TABLE isolates
    RENAME COLUMN mic_ery_1 TO mic_ery_I;
ALTER TABLE isolates
    RENAME COLUMN mic_str_1 TO mic_str_I;
ALTER TABLE isolates
    RENAME COLUMN mic_tet_1 TO mic_tet_I;
ALTER TABLE isolates
    RENAME COLUMN mic_tmpsmx_1 TO mic_tmpsmx_I;
ALTER TABLE isolates
    RENAME COLUMN mic_van_1 TO mic_van_I;

-- migrate:down

ALTER TABLE isolates
    ADD COLUMN latitude double precision,
    ADD COLUMN longitude double precision,
    DROP COLUMN symptom_asymptomatic,
    DROP COLUMN symptom_gastroenteritis,
    DROP COLUMN symptom_sepsis,
    DROP COLUMN symptom_urinary_tract_infection,
    DROP COLUMN symptom_unknown,
    ADD COLUMN clinical_info text,
    DROP COLUMN mic_azm_I,
    DROP COLUMN mic_smx,
    DROP COLUMN mic_tgc_I,
    DROP COLUMN mic_tmp_I,
    ALTER COLUMN mic_azm TYPE text USING mic_azm::text;
ALTER TABLE isolates
    RENAME COLUMN mic_cox_I TO mic_cox_1;
ALTER TABLE isolates
    RENAME COLUMN mic_chl_I	TO mic_chl_1;
ALTER TABLE isolates
    RENAME COLUMN mic_cip_I TO mic_cip_1;
ALTER TABLE isolates
    RENAME COLUMN mic_pen_I TO mic_pen_1;
ALTER TABLE isolates
    RENAME COLUMN mic_rif_I TO mic_rif_1;
ALTER TABLE isolates
    RENAME COLUMN mic_amo_I TO mic_amo_1;
ALTER TABLE isolates
    RENAME COLUMN mic_amp_I TO mic_amp_1;
ALTER TABLE isolates
    RENAME COLUMN mic_caz_I TO mic_caz_1;
ALTER TABLE isolates
    RENAME COLUMN mic_col_I TO mic_col_1;
ALTER TABLE isolates
    RENAME COLUMN mic_etp_I TO mic_etp_1;
ALTER TABLE isolates
    RENAME COLUMN mic_gmn_I TO mic_gmn_1;
ALTER TABLE isolates
    RENAME COLUMN mic_mem_I TO mic_mem_1;
ALTER TABLE isolates
    RENAME COLUMN mic_smx_I TO mic_smx_1;
ALTER TABLE isolates
    RENAME COLUMN mic_ery_I TO mic_ery_1;
ALTER TABLE isolates
    RENAME COLUMN mic_str_I TO mic_str_1;
ALTER TABLE isolates
    RENAME COLUMN mic_tet_I TO mic_tet_1;
ALTER TABLE isolates
    RENAME COLUMN mic_tmpsmx_I TO mic_tmpsmx_1;
ALTER TABLE isolates
    RENAME COLUMN mic_van_I TO mic_van_1;