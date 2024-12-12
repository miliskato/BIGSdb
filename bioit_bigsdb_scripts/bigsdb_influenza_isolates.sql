INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) VALUES('html', 'text', 'galaxy report', 'galaxy html report', 't', 't', (SELECT CURRENT_DATE), 1) ON CONFLICT DO NOTHING;
INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) VALUES('assembly', 'text', 'galaxy report', '', 't', 't', (SELECT CURRENT_DATE), 1) ON CONFLICT DO NOTHING;
INSERT INTO eav_fields(field, value_format, category, description, no_curate, no_submissions, datestamp, curator) VALUES('influenza_subtype', 'text', 'Nextclade', '', 't', 't', (SELECT CURRENT_DATE), 1) ON CONFLICT DO NOTHING;

INSERT INTO eav_fields_hidden(field, value_format, description, no_curate, no_submissions, datestamp, curator) VALUES('hash_fastq_md5_forward', 'text', '', 't', 't', (SELECT CURRENT_DATE), 1) ON CONFLICT DO NOTHING;
INSERT INTO eav_fields_hidden(field, value_format, description, no_curate, no_submissions, datestamp, curator) VALUES('hash_fastq_md5_reverse', 'text', '', 't', 't', (SELECT CURRENT_DATE), 1) ON CONFLICT DO NOTHING;
INSERT INTO eav_fields_hidden(field, value_format, description, no_curate, no_submissions, datestamp, curator) VALUES('hash_fasta_md5', 'text', '', 't', 't', (SELECT CURRENT_DATE), 1) ON CONFLICT DO NOTHING;
INSERT INTO eav_fields_hidden(field, value_format, description, no_curate, no_submissions, datestamp, curator) VALUES('mongo_results_version', 'text', '', 't', 't', (SELECT CURRENT_DATE), 1) ON CONFLICT DO NOTHING;
