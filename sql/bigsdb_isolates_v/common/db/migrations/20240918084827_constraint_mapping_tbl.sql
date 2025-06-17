-- migrate:up
ALTER TABLE mapping_table
ADD COLUMN isolate_id integer NOT NULL UNIQUE;

ALTER TABLE mapping_table
ADD CONSTRAINT existing_isolate FOREIGN KEY (isolate_id) REFERENCES isolates (id)
ON DELETE CASCADE;

-- migrate:down

ALTER TABLE mapping_table DROP CONSTRAINT existing_isolate;
ALTER TABLE mapping_table DROP COLUMN isolate_id;

