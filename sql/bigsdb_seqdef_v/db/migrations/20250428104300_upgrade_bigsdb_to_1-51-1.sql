-- migrate: up
UPDATE db_attributes SET value='51' WHERE field='version';

ALTER TABLE users ADD country text;
ALTER TABLE users ADD sector text;

GRANT USAGE, CREATE ON SCHEMA public TO apache;

-- migrate: down
UPDATE db_attributes SET value='47' WHERE field='version';

ALTER TABLE users DROP COLUMN country;
ALTER TABLE users DROP COLUMN sector;

REVOKE USAGE, CREATE ON SCHEMA public FROM apache;

