-- migrate:up
CREATE TABLE alerts (
id text NOT NULL,
type text NOT NULL,
method text NULL,
submitter int NOT NULL,
date_submitted date NOT NULL,
datestamp date NOT NULL,
status text NOT NULL,
curator int,
outcome text,
email boolean,
PRIMARY KEY(id),
CONSTRAINT s_submitter FOREIGN KEY (submitter) REFERENCES users
ON DELETE CASCADE
ON UPDATE CASCADE,
CONSTRAINT s_curator FOREIGN KEY (curator) REFERENCES users
ON DELETE CASCADE
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON alerts TO apache;

CREATE TABLE alert_details (
alert_id text NOT NULL,
index int NOT NULL,
field text NOT NULL,
value text,
PRIMARY KEY(alert_id,index,field),
CONSTRAINT io_alert_id FOREIGN KEY (alert_id) REFERENCES alerts
ON DELETE CASCADE
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON alert_details TO apache;

CREATE TABLE alert_details_field_order (
alert_id text NOT NULL,
field text NOT NULL,
index int NOT NULL,
PRIMARY KEY(alert_id,field),
CONSTRAINT iofo_alert_id FOREIGN KEY (alert_id) REFERENCES alerts
ON DELETE CASCADE
ON UPDATE CASCADE
);

GRANT SELECT,UPDATE,INSERT,DELETE ON alert_details_field_order TO apache;

-- migrate:down
DROP TABLE alert_details_field_order;
DROP TABLE alert_details;
DROP TABLE alerts;