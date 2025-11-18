-- migrate:up
ALTER TABLE isolates
    ADD COLUMN internal_lims_id text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN internal_lims_id;