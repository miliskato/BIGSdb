-- migrate:up
ALTER TABLE isolates
    ADD COLUMN serogroup_agglutination text,
    ADD COLUMN serogroup_pcr text,
    ADD COLUMN meningococcal_vaccination text,
    ADD COLUMN meningococcal_vaccine text,
    ADD COLUMN meningococcal_vaccination_year int,
    ADD COLUMN streptococcal_vaccination text,
    ADD COLUMN streptococcal_vaccine text,
    ADD COLUMN streptococcal_vaccination_year int,
    ADD COLUMN symptom_unknown text,
    ADD COLUMN symptom_other text,
    ADD COLUMN symptom_meningitis text,
    ADD COLUMN symptom_bacterial_septicemia text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN serogroup_agglutination,
    DROP COLUMN serogroup_pcr,
    DROP COLUMN meningococcal_vaccination,
    DROP COLUMN meningococcal_vaccine,
    DROP COLUMN meningococcal_vaccination_year,
    DROP COLUMN streptococcal_vaccination,
    DROP COLUMN streptococcal_vaccine,
    DROP COLUMN streptococcal_vaccination_year,
    DROP COLUMN symptom_unknown,
    DROP COLUMN symptom_other,
    DROP COLUMN symptom_meningitis,
    DROP COLUMN symptom_bacterial_septicemia;