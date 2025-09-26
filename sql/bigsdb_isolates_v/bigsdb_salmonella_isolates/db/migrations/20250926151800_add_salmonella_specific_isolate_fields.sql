-- migrate:up
ALTER TABLE isolates
    ADD COLUMN assembly text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN assembly;