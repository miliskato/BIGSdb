-- migrate:up
ALTER TABLE isolates
    DROP COLUMN country_reporting_alert;

-- migrate:down
ALTER TABLE isolates
    ADD COLUMN country_reporting_alert text;