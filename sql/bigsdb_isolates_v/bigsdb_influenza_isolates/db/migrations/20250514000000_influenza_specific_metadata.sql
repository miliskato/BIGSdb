-- migrate:up
ALTER TABLE isolates
    ADD COLUMN FluA_SubtypeHAPCR text,
    ADD COLUMN FluA_SubtypeNAPCR text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN FluA_SubtypeHAPCR,
    DROP COLUMN FluA_SubtypeNAPCR;