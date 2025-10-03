-- migrate:up
ALTER TABLE isolates
    ADD COLUMN html text,
    ADD COLUMN pipeline text,
    ADD COLUMN assembly text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN html,
    DROP COLUMN pipeline,
    DROP COLUMN assembly;