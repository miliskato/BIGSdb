-- migrate:up
ALTER TABLE isolates
    ADD COLUMN patient_first_name text,
    ADD COLUMN patient_last_name text,
    ADD COLUMN physician_name text,
    ADD COLUMN sampling_date date,
    ADD COLUMN reception_date date,
    ADD COLUMN positive_culture_date date,
    ADD COLUMN identification_BK text,
    ADD COLUMN identification_NTM text,
    ADD COLUMN isoniazid_0_1ug text,
    ADD COLUMN rifampicin_1ug text,
    ADD COLUMN ethambutol_5ug text,
    ADD COLUMN pyrazinamid_100ug text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN patient_first_name,
    DROP COLUMN patient_last_name,
    DROP COLUMN physician_name,
    DROP COLUMN sampling_date,
    DROP COLUMN reception_date,
    DROP COLUMN positive_culture_date,
    DROP COLUMN identification_BK,
    DROP COLUMN identification_NTM,
    DROP COLUMN isoniazid_0_1ug,
    DROP COLUMN rifampicin_1ug,
    DROP COLUMN ethambutol_5ug,
    DROP COLUMN pyrazinamid_100ug;
