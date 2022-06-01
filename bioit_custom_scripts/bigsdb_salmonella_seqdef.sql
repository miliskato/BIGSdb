-- INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp)
-- VALUES(1, 'MLST', 'MLST scheme downloaded and updated weekly from the Pasteur-institute Bigsdb-interface.', 't', 1, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
-- INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp)
-- VALUES(2, 'cgMLST', 'cgMLST scheme downloaded and updated weekly from the Pasteur-institute Bigsdb-interface.', 't', 2, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
-- INSERT INTO scheme_fields(scheme_id, field, type, description, field_order, dropdown, primary_key, curator, datestamp)
--  VALUES(1, 'ST', 'integer', 'Sequence Type', 1, 'f', 't', 1, (SELECT CURRENT_DATE));
-- amr
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(3, 'NCBI_AMR', 'NDARO AMR database', 't', 3, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(4, 'ResFinder', 'ResFinder database', 't', 4, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
-- other genedetection
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(5, 'PlasmidFinder_entero', 'PlasmidFinder enterobacteriaceae', 't', 5, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(6, 'VFDB_core', 'VirulenceFactor core database', 't', 6, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
--pointfinder
INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, no_submissions, curator, date_entered, datestamp) VALUES('POINTFINDER_SPECTINOMYCIN','DNA','text','t', 't','t', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, no_submissions, curator, date_entered, datestamp) VALUES('POINTFINDER_CIPROFLOXACIN','DNA','text','t', 't','t', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, no_submissions, curator, date_entered, datestamp) VALUES('POINTFINDER_COLISTIN','DNA','text','t', 't','t', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, no_submissions, curator, date_entered, datestamp) VALUES('POINTFINDER_NALIDIXIC_ACID','DNA','text','t', 't','t', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO loci(id, data_type, allele_id_format, length_varies, coding_sequence, no_submissions, curator, date_entered, datestamp) VALUES('POINTFINDER_UNKNOWN','DNA','text','t', 't','t', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) VALUES((SELECT id FROM schemes WHERE name='Pointfinder'), 'POINTFINDER_SPECTINOMYCIN', 1, (SELECT CURRENT_DATE));
INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) VALUES((SELECT id FROM schemes WHERE name='Pointfinder'), 'POINTFINDER_CIPROFLOXACIN', 1, (SELECT CURRENT_DATE));
INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) VALUES((SELECT id FROM schemes WHERE name='Pointfinder'), 'POINTFINDER_COLISTIN', 1, (SELECT CURRENT_DATE));
INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) VALUES((SELECT id FROM schemes WHERE name='Pointfinder'), 'POINTFINDER_NALIDIXIC_ACID', 1, (SELECT CURRENT_DATE));
INSERT INTO scheme_members(scheme_id, locus, curator, datestamp) VALUES((SELECT id FROM schemes WHERE name='Pointfinder'), 'POINTFINDER_UNKNOWN', 1, (SELECT CURRENT_DATE));
--spifinder
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(7, 'spifinder_fasta', 'SPIFinder with assembly', 't', 7, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(8, 'spifinder_fastq', 'SPIFinder with raw reads', 't', 8, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
--serotyping
--sistr
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(9,'sistr', 'SISTR ', 't', 9, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
--seqsero2 allele
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(11,'seqsero2', 'SeqSero2 allele ', 't', 11, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
--seqsero2 kmer
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(13,'seqsero2_kmer', 'SeqSero2 kmer ', 't', 13, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
--seqsero2 kmerread
INSERT INTO schemes(id, name, description, allow_missing_loci, display_order, no_submissions, disable, curator, date_entered, datestamp) VALUES(15,'seqsero2_kmerread', 'SeqSero2 kmerread ', 't', 15, 't', 'f', 1, (SELECT CURRENT_DATE), (SELECT CURRENT_DATE));
