-- migrate:up
ALTER TABLE log ADD COLUMN client text;
ALTER TABLE log ADD COLUMN user_name text;

-- migrate:down
ALTER TABLE log DROP COLUMN client;
ALTER TABLE log DROP COLUMN user_name;
