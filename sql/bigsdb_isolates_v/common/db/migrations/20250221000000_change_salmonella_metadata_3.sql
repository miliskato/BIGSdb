-- migrate:up
ALTER TABLE isolates
    DROP COLUMN link,
    ADD COLUMN link_human_to_human_transmission text,
    ADD COLUMN link_isolated_case text,
    ADD COLUMN link_foodborne_transmission text,
    ADD COLUMN link_not_applicable text,
    ADD COLUMN link_other text,
    ADD COLUMN link_unknown text,
    ADD COLUMN serovar_luminex text,
    DROP COLUMN aggl_serogroup,
    ADD COLUMN serovar_agglutination text,
    ADD COLUMN serovar_agglutination_formula text,
    ADD COLUMN malditof_identification text;

-- migrate:down
ALTER TABLE isolates
    ADD COLUMN link text,
    DROP COLUMN link_human_to_human_transmission,
    DROP COLUMN link_isolated_case,
    DROP COLUMN link_foodborne_transmission,
    DROP COLUMN link_not_applicable,
    DROP COLUMN link_other,
    DROP COLUMN link_unknown,
    DROP COLUMN serovar_luminex,
    DROP COLUMN serovar_agglutination,
    ADD COLUMN aggl_serogroup text,
    DROP COLUMN serovar_agglutination_formula,
    DROP COLUMN malditof_identification;