-- migrate:up
ALTER TABLE isolates
    ADD COLUMN mic_resistances text,
    ADD COLUMN serogroup_pheno text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN mic_resistances,
    DROP COLUMN serogroup_pheno;