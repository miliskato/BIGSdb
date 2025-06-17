-- migrate:up
CREATE TYPE hospital_unit_type AS ENUM ('PEDSICU', 'ICU', 'INFECT', 'INTMED', 'O', 'OBGYN', 'ED',
    'PEDS', 'GERIATRIE', 'SURG', 'UNK', 'URO', 'EXTMUROS', 'PNEUMO', 'DIALNEF', 'REVA', 'ONCOL');
CREATE TYPE lin_gen_type AS ENUM ('CFR', 'CFRB', 'OPTRA', 'POXTA', 'POXTA-EF', '23S1', '23S2', 'O', 'UNK', 'NA');
CREATE TYPE pathogen_defined_type AS ENUM ('ENCFAE', 'ENCFAI', 'ENCGALL', 'ENCCASS', 'ENCDUR', 'ENCRAFF', 'ENC', 'O', 'NA', 'UNK', 'ENCAVI');
CREATE TYPE patient_type_type AS ENUM ('INPAT','O','OUTPAT', 'UNK');
CREATE TYPE mic_sign_type AS ENUM ('<', '<=', '=', '>=', '>');
CREATE TYPE vangenes_type AS ENUM ('VANA', 'VANB', 'VANC', 'VAND', 'VANE', 'VANG', 'VANAC', 'VANBC', 'O', 'UNK', 'NA', 'VANAB');
CREATE TYPE specimen_type AS ENUM ('BLOOD', 'CSF', 'BRONCHTRACH', 'ABDO', 'PERITONEAL', 'WOUND', 'TISSUE', 'THROAT', 'SKIN',
    'EAR', 'NONSTERILE', 'OTHERSTERILE', 'SCREENING', 'SALIVA', 'URINE', 'UNK', 'NA');

ALTER TABLE isolates ALTER COLUMN specimen SET DATA TYPE specimen_type;

ALTER TABLE isolates
    ADD COLUMN symptom_otitis boolean,
    ADD COLUMN symptom_pharyngitis boolean,
    ADD COLUMN symptom_septicemia boolean,
    ADD COLUMN symptom_osteomyelitis boolean,
    ADD COLUMN symptom_myositis boolean,
    ADD COLUMN symptom_wound_infection boolean,
    ADD COLUMN symptom_pneumonia boolean,
    ADD COLUMN symptom_monoarthritis boolean,
    ADD COLUMN symptom_cellulitis boolean,
    ADD COLUMN symptom_puerperale_sepsis boolean,
    ADD COLUMN symptom_meningitis boolean,
    ADD COLUMN symptom_polyarthritis boolean,
    ADD COLUMN symptom_urine boolean,
    ADD COLUMN symptom_peritonitis boolean,
    ADD COLUMN symptom_endocarditis boolean,
    ADD COLUMN symptom_fasciitis boolean,
    ADD COLUMN symptom_other text,
    ADD COLUMN symptom_unknown text,
    ADD COLUMN symptom_screening text,
    ADD COLUMN hospital_unit hospital_unit_type,
    ADD COLUMN institution text,
    ADD COLUMN lab_name_code int,
    ADD COLUMN lin_gen lin_gen_type,
    ADD COLUMN outbreak boolean,
    ADD COLUMN pathogen pathogen_defined_type,
    ADD COLUMN patient_type patient_type_type,
    ADD COLUMN mic_amo_sign mic_sign_type,
    ADD COLUMN mic_amo real,
    ADD COLUMN mic_amo_I text,
    ADD COLUMN mic_dap_sign mic_sign_type,
    ADD COLUMN mic_dap real,
    ADD COLUMN mic_dap_I text,
    ADD COLUMN mic_era_sign mic_sign_type,
    ADD COLUMN mic_era real,
    ADD COLUMN mic_era_I text,
    ADD COLUMN mic_gen_sign mic_sign_type,
    ADD COLUMN mic_gen real,
    ADD COLUMN mic_gen_I text,
    ADD COLUMN mic_lin_sign mic_sign_type,
    ADD COLUMN mic_lin real,
    ADD COLUMN mic_lin_I text,
    ADD COLUMN mic_tec_sign mic_sign_type,
    ADD COLUMN mic_tec real,
    ADD COLUMN mic_tec_I text,
    ADD COLUMN mic_tig_sign mic_sign_type,
    ADD COLUMN mic_tig real,
    ADD COLUMN mic_tig_I text,
    ADD COLUMN mic_van_sign mic_sign_type,
    ADD COLUMN mic_van real,
    ADD COLUMN mic_van_I text,
    ADD COLUMN subject text,
    ADD COLUMN vangenes vangenes_type;

-- migrate:down

ALTER TABLE isolates ALTER COLUMN specimen SET DATA TYPE text;

DROP TYPE hospital_unit_type;
DROP TYPE lin_gen_type;
DROP TYPE pathogen_defined_type;
DROP TYPE patient_type_type;
DROP TYPE mic_sign_type;
DROP TYPE vangenes_type;
DROP TYPE specimen_type;

ALTER TABLE isolates
    DROP COLUMN symptom_otitis,
    DROP COLUMN symptom_pharyngitis,
    DROP COLUMN symptom_septicemia,
    DROP COLUMN symptom_osteomyelitis,
    DROP COLUMN symptom_myositis,
    DROP COLUMN symptom_wound_infection,
    DROP COLUMN symptom_pneumonia,
    DROP COLUMN symptom_monoarthritis,
    DROP COLUMN symptom_cellulitis,
    DROP COLUMN symptom_puerperale_sepsis,
    DROP COLUMN symptom_meningitis,
    DROP COLUMN symptom_polyarthritis,
    DROP COLUMN symptom_urine,
    DROP COLUMN symptom_peritonitis,
    DROP COLUMN symptom_endocarditis,
    DROP COLUMN symptom_fasciitis,
    DROP COLUMN symptom_other,
    DROP COLUMN symptom_unknown,
    DROP COLUMN symptom_screening,
    DROP COLUMN hospital_unit,
    DROP COLUMN institution,
    DROP COLUMN lab_name_code,
    DROP COLUMN lin_gen,
    DROP COLUMN outbreak,
    DROP COLUMN pathogen,
    DROP COLUMN patient_type,
    DROP COLUMN mic_amo_sign,
    DROP COLUMN mic_amo,
    DROP COLUMN mic_amo_I,
    DROP COLUMN mic_dap_sign,
    DROP COLUMN mic_dap,
    DROP COLUMN mic_dap_I,
    DROP COLUMN mic_era_sign,
    DROP COLUMN mic_era,
    DROP COLUMN mic_era_I,
    DROP COLUMN mic_gen_sign,
    DROP COLUMN mic_gen,
    DROP COLUMN mic_gen_I,
    DROP COLUMN mic_lin_sign,
    DROP COLUMN mic_lin,
    DROP COLUMN mic_lin_I,
    DROP COLUMN mic_tec_sign,
    DROP COLUMN mic_tec,
    DROP COLUMN mic_tec_I,
    DROP COLUMN mic_tig_sign,
    DROP COLUMN mic_tig,
    DROP COLUMN mic_tig_I,
    DROP COLUMN mic_van_sign,
    DROP COLUMN mic_van,
    DROP COLUMN mic_van_I,
    DROP COLUMN subject,
    DROP COLUMN vangenes;