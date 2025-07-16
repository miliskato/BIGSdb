-- migrate:up
CREATE TABLE mapping_table (
isolate text NOT NULL,
pseudo_id text NOT NULL,
PRIMARY KEY(isolate)
);

GRANT SELECT,UPDATE,INSERT,DELETE ON mapping_table TO apache;

-- migrate:down
DROP TABLE mapping_table;