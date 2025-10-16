-- migrate:up
ALTER TABLE isolates
    ADD COLUMN html text,
    ADD COLUMN assembly text,
    ADD COLUMN pipeline text,
    ADD COLUMN mongo_results_version text,
    ADD COLUMN coverage_assembly text,
    ADD COLUMN coverage_reference text,
    ADD COLUMN positions_covered_1x_assembly text,
    ADD COLUMN positions_covered_1x_reference text;

-- migrate:down
ALTER TABLE isolates
    DROP COLUMN html,
    DROP COLUMN assembly,
    DROP COLUMN pipeline,
    DROP COLUMN mongo_results_version,
    DROP COLUMN coverage_assembly,
    DROP COLUMN coverage_reference,
    DROP COLUMN positions_covered_1x_assembly,
    DROP COLUMN positions_covered_1x_reference;
