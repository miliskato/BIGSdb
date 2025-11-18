-- migrate:up
ALTER TABLE isolates
    ADD COLUMN internal_LIMS_id text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN internal_LIMS_id;