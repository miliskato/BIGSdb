-- migrate:up
ALTER TABLE isolates
    ADD COLUMN FluA_SubtypeHAPCR text,
    ADD COLUMN FluA_SubtypeNAPCR text,
    ADD COLUMN Flu_subtype_or_lineagePCR text;
ALTER TABLE isolates
    DROP COLUMN FluA_subtypePCR,
    DROP COLUMN FluB_lineagePCR;


-- migrate:down
ALTER TABLE isolates
    DROP COLUMN FluA_SubtypeHAPCR,
    DROP COLUMN FluA_SubtypeNAPCR,
    DROP COLUMN Flu_subtype_or_lineagePCR;
ALTER TABLE isolates
    ADD COLUMN FluA_subtypePCR text,
    ADD COLUMN FluB_lineagePCR text;