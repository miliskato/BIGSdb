-- migrate:up
ALTER TABLE isolates
    ADD COLUMN html text,
    ADD COLUMN pipeline text,
    ADD COLUMN mongo_results_version text;

DROP TABLE eav_text_hidden;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN html,
    DROP COLUMN pipeline,
    DROP COLUMN mongo_results_version;

CREATE TABLE eav_fields_hidden AS (SELECT * FROM eav_fields) WITH NO DATA;
ALTER TABLE eav_fields_hidden ADD PRIMARY KEY(field);
GRANT SELECT, INSERT, UPDATE, DELETE ON eav_fields_hidden TO apache;
CREATE TABLE eav_text_hidden AS (SELECT * FROM eav_text) WITH NO DATA;
ALTER TABLE eav_text_hidden ADD PRIMARY KEY(isolate_id, field);
ALTER TABLE eav_text_hidden ADD CONSTRAINT eavt_field FOREIGN KEY (field) REFERENCES eav_fields_hidden(field) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE eav_text_hidden ADD CONSTRAINT eavt_isolate FOREIGN KEY (isolate_id) REFERENCES isolates(id) ON UPDATE CASCADE ON DELETE CASCADE;
GRANT SELECT, INSERT, UPDATE, DELETE ON eav_text_hidden TO apache;