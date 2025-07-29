-- migrate:up
ALTER TABLE isolates
    ADD COLUMN fluA_SubtypeHAPCR text,
    ADD COLUMN fluA_SubtypeNAPCR text,
    ADD COLUMN flu_subtype_or_lineagePCR text;
ALTER TABLE isolates
    DROP COLUMN fluA_subtypePCR,
    DROP COLUMN fluB_lineagePCR;


-- migrate:down
ALTER TABLE isolates
    DROP COLUMN fluA_SubtypeHAPCR,
    DROP COLUMN fluA_SubtypeNAPCR,
    DROP COLUMN flu_subtype_or_lineagePCR;
ALTER TABLE isolates
    ADD COLUMN fluA_subtypePCR text,
    ADD COLUMN fluB_lineagePCR text;