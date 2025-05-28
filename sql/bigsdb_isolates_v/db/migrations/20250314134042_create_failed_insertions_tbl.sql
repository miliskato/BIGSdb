-- migrate:up
CREATE TABLE failed_insertions (
        message_id text NOT NULL,
        pseudo_id text NOT NULL,
        timestamp timestamp,
        comment text
);

GRANT SELECT,UPDATE,INSERT,DELETE ON failed_insertions TO apache;

-- migrate:down
DROP TABLE failed_insertions;
