-- migrate:up
ALTER TABLE isolates
    ADD COLUMN under_treatment text,
    ADD COLUMN tuberculosis_antecedents text,
    ADD COLUMN tuberculosis_site text,
    ADD COLUMN tuberculosis_suspicion text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN under_treatment,
    DROP COLUMN tuberculosis_antecedents,
    DROP COLUMN tuberculosis_site,
    DROP COLUMN tuberculosis_suspicion;