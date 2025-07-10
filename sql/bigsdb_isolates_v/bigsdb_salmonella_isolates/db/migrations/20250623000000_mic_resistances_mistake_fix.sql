-- migrate:up
ALTER TABLE isolates
    ADD COLUMN mic_resistances text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN mic_resistances;