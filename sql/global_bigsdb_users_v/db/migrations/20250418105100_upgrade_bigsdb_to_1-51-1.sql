-- migrate: up

ALTER TABLE users ADD sector text;
ALTER TABLE users ADD country text;

-- migrate: down

ALTER TABLE users DROP COLUMN sector;
ALTER TABLE users DROP COLUMN country;