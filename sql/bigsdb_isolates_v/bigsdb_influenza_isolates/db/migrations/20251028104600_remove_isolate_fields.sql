-- migrate:up
ALTER TABLE isolates
    DROP COLUMN assembly,
    ADD COLUMN consensus_sequence text,
    DROP COLUMN coverage_assembly,
    DROP COLUMN coverage_reference,
    DROP COLUMN positions_covered_1x_assembly,
    DROP COLUMN positions_covered_1x_reference;

-- migrate:down
ALTER TABLE isolates
    ADD COLUMN assembly text,
    DROP COLUMN consensus_sequence,
    ADD COLUMN coverage_assembly text,
    ADD COLUMN coverage_reference text,
    ADD COLUMN positions_covered_1x_assembly text,
    ADD COLUMN positions_covered_1x_reference text;