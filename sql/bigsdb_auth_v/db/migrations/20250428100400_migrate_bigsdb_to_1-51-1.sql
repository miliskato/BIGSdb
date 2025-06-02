-- migrate:up
ALTER TABLE users ADD COLUMN update_profile boolean;

ALTER TABLE sessions ADD COLUMN update_profile boolean;

ALTER TABLE clients
    ADD dbase text,
    ADD username text,
    ADD CONSTRAINT c_dbase_user FOREIGN KEY(username,dbase) REFERENCES users(name,dbase) ON UPDATE CASCADE ON DELETE CASCADE,
    DROP CONSTRAINT clients_pkey,
    ADD PRIMARY KEY(client_id);

GRANT INSERT,UPDATE,DELETE ON clients TO apache;

-- migrate:down
ALTER TABLE users DROP COLUMN update_profile;

ALTER TABLE sessions DROP COLUMN update_profile;

ALTER TABLE clients
    DROP COLUMN dbase,
    DROP COLUMN username,
    DROP CONSTRAINT clients_pkey,
    ADD PRIMARY KEY(application,version);

REVOKE INSERT,UPDATE,DELETE ON clients FROM apache;