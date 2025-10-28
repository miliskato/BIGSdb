-- migrate:up
ALTER TABLE submissions
    ADD COLUMN warning_reasons text;

ALTER TABLE isolate_submission_isolates
    DROP COLUMN quality,
    DROP COLUMN resequencing;

-- migrate:down
ALTER TABLE submissions
    DROP COLUMN warning_reasons;

ALTER TABLE isolate_submission_isolates
    ADD COLUMN quality text,
    ADD COLUMN resequencing text;
