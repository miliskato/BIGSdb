-- migrate:up
CREATE TABLE rejected_isolates (
id int NOT NULL,
isolate text NOT NULL,
insertion_date date NOT NULL,
archival_date date,
rejection_reasons text NOT NULL,
insertion_type text NOT NULL,
report_link text NOT NULL,
status text NOT NULL,
curator int,
PRIMARY KEY(id)
);

GRANT SELECT,UPDATE,INSERT,DELETE ON rejected_isolates TO apache;

-- migrate:down
DROP TABLE rejected_isolates;