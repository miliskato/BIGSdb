
-- migrate:up
ALTER TABLE isolates DROP COLUMN label;
ALTER TABLE isolates ADD COLUMN country text,
                    ADD COLUMN isolate_label text;

-- migrate:down
ALTER TABLE isolates DROP COLUMN isolate_label,
                    DROP COLUMN country;
ALTER TABLE isolates ADD COLUMN label text;

