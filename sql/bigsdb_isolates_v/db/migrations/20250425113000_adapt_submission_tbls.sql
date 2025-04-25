-- migrate:up
ALTER TABLE submissions
    DROP COLUMN validation_type,
    ADD COLUMN quality text,
    ADD COLUMN resequencing text;

-- migrate:down
ALTER TABLE submissions
    ADD COLUMN validation_type text,
    DROP COLUMN quality text,
    DROP COLUMN resequencing text;

-- migrate:up
ALTER TABLE isolate_submission_isolates,
    ADD COLUMN quality text,
    ADD COLUMN resequencing text;

-- migrate:down
ALTER TABLE isolate_submission_isolates,
    DROP COLUMN quality text,
    DROP COLUMN resequencing text;
