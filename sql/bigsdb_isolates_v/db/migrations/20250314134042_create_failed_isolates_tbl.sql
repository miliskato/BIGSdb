-- migrate:up
CREATE TABLE failed_isolates (
        message_id text NOT NULL,
        pseudo_id text NOT NULL,
        timestamp timestamp,
        comment text
);

-- migrate:down
DROP TABLE failed_isolates;
