-- migrate:up
ALTER TABLE isolates
    ADD COLUMN reference_database text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN reference_database;
